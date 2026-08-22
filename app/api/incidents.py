from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.models import Incident
from app.rest_schemas import IncidentDetailOut, IncidentOut
from app.tracing.engine import run_tracing

router = APIRouter(tags=["incidents"])


def _to_out(incident: Incident, node_ids: list[str]) -> IncidentDetailOut:
    causes = incident.candidate_causes or []
    top_confidence = causes[0]["confidence"] if causes else None
    return IncidentDetailOut(
        id=str(incident.id),
        status=incident.status,
        contaminant_id=incident.contaminant_id,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
        affected_node_count=len(node_ids),
        top_confidence=top_confidence,
        candidate_causes=causes,
        node_ids=node_ids,
    )


@router.get("/incidents", response_model=list[IncidentOut])
async def list_incidents(session: AsyncSession = Depends(get_session)):
    rows = (
        (await session.execute(select(Incident).options(selectinload(Incident.nodes)).order_by(Incident.updated_at.desc())))
        .scalars()
        .all()
    )
    return [_to_out(i, [n.node_id for n in i.nodes]) for i in rows]


@router.get("/incidents/{incident_id}", response_model=IncidentDetailOut)
async def get_incident(incident_id: str, session: AsyncSession = Depends(get_session)):
    incident = (
        await session.execute(select(Incident).options(selectinload(Incident.nodes)).where(Incident.id == incident_id))
    ).scalar_one_or_none()
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return _to_out(incident, [n.node_id for n in incident.nodes])


@router.post("/incidents/trace", response_model=list[IncidentOut])
async def trigger_trace(contaminant_id: str, window: Optional[float] = None, session: AsyncSession = Depends(get_session)):
    incidents = await run_tracing(contaminant_id, window_seconds=window)
    # run_tracing appends once per node that triggered record_incident_candidate, and nodes
    # sharing one episode merge into the same Incident -- dedupe before re-fetching each one
    seen_ids = {incident.id for incident in incidents}
    out = []
    for incident_id in seen_ids:
        refreshed = (
            await session.execute(select(Incident).options(selectinload(Incident.nodes)).where(Incident.id == incident_id))
        ).scalar_one()
        out.append(_to_out(refreshed, [n.node_id for n in refreshed.nodes]))
    out.sort(key=lambda i: i.updated_at, reverse=True)
    return out
