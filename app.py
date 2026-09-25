from __future__ import annotations

import os
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Generator

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

database_url = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'ritmox.db'}")
if database_url.startswith("postgres://"):
    database_url = "postgresql+psycopg://" + database_url[len("postgres://"):]
elif database_url.startswith("postgresql://") and "+psycopg" not in database_url:
    database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]

engine = create_engine(
    database_url,
    connect_args={"check_same_thread": False} if database_url.startswith("sqlite:") else {},
    pool_pre_ping=True,
)
DB = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Workout(Base):
    __tablename__ = "workouts"
    id: Mapped[int] = mapped_column(primary_key=True)
    modality: Mapped[str] = mapped_column(String(40), default="musculacao")
    title: Mapped[str] = mapped_column(String(160))
    subtitle: Mapped[str] = mapped_column(String(220), default="")
    duration_min: Mapped[int] = mapped_column(Integer, default=45)
    started: Mapped[bool] = mapped_column(Boolean, default=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    exercises: Mapped[list["Exercise"]] = relationship(back_populates="workout", cascade="all, delete-orphan")


class Exercise(Base):
    __tablename__ = "exercises"
    id: Mapped[int] = mapped_column(primary_key=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("workouts.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    muscle: Mapped[str] = mapped_column(String(120), default="")
    sets_total: Mapped[int] = mapped_column(Integer, default=4)
    reps: Mapped[str] = mapped_column(String(30), default="8-10")
    load_kg: Mapped[float] = mapped_column(Float, default=0)
    sets_done: Mapped[int] = mapped_column(Integer, default=0)
    workout: Mapped[Workout] = relationship(back_populates="exercises")


class RunActivity(Base):
    __tablename__ = "run_activities"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160), default="Corrida Matinal")
    distance_km: Mapped[float] = mapped_column(Float, default=5.02)
    duration_sec: Mapped[int] = mapped_column(Integer, default=1716)
    avg_pace: Mapped[str] = mapped_column(String(16), default="5:42")
    calories: Mapped[int] = mapped_column(Integer, default=432)
    avg_hr: Mapped[int] = mapped_column(Integer, default=162)
    elevation_m: Mapped[int] = mapped_column(Integer, default=5)
    source: Mapped[str] = mapped_column(String(30), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Modality(Base):
    __tablename__ = "modalities"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    icon: Mapped[str] = mapped_column(String(16), default="●")
    active: Mapped[bool] = mapped_column(Boolean, default=True)



class WorkoutPlan(Base):
    __tablename__ = "workout_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    planned_date: Mapped[str] = mapped_column(String(10), index=True)
    title: Mapped[str] = mapped_column(String(160))
    modality: Mapped[str] = mapped_column(String(40), default="musculacao")
    duration_min: Mapped[int] = mapped_column(Integer, default=45)
    notes: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    exercises: Mapped[list["PlannedExercise"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="PlannedExercise.position"
    )
    blocks: Mapped[list["PlannedBlock"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="PlannedBlock.position"
    )


class PlannedExercise(Base):
    __tablename__ = "planned_exercises"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("workout_plans.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(160))
    muscle: Mapped[str] = mapped_column(String(120), default="")
    sets_total: Mapped[int] = mapped_column(Integer, default=4)
    reps: Mapped[str] = mapped_column(String(30), default="8-10")
    load_kg: Mapped[float] = mapped_column(Float, default=0)
    plan: Mapped[WorkoutPlan] = relationship(back_populates="exercises")


class PlannedBlock(Base):
    __tablename__ = "planned_blocks"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("workout_plans.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str] = mapped_column(String(40), default="strength")
    name: Mapped[str] = mapped_column(String(160), default="")
    detail: Mapped[str] = mapped_column(String(160), default="")
    sets_total: Mapped[int] = mapped_column(Integer, default=0)
    reps: Mapped[str] = mapped_column(String(30), default="")
    load_kg: Mapped[float] = mapped_column(Float, default=0)
    distance_km: Mapped[float] = mapped_column(Float, default=0)
    duration_min: Mapped[int] = mapped_column(Integer, default=0)
    pace_target: Mapped[str] = mapped_column(String(30), default="")
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    rest_sec: Mapped[int] = mapped_column(Integer, default=0)
    intensity: Mapped[str] = mapped_column(String(40), default="")
    plan: Mapped[WorkoutPlan] = relationship(back_populates="blocks")



class HealthAssessment(Base):
    __tablename__ = "health_assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    risk_status: Mapped[str] = mapped_column(String(40), default="screening_complete")
    red_flags_json: Mapped[str] = mapped_column(Text, default="[]")
    professional_clearance: Mapped[bool] = mapped_column(Boolean, default=False)
    clearance_provider: Mapped[str] = mapped_column(String(160), default="")
    clearance_date: Mapped[str] = mapped_column(String(10), default="")
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ClearanceRequest(Base):
    __tablename__ = "clearance_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("health_assessments.id", ondelete="CASCADE"), index=True)
    professional_name: Mapped[str] = mapped_column(String(160), default="")
    professional_email: Mapped[str] = mapped_column(String(220), default="")
    message: Mapped[str] = mapped_column(String(800), default="")
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    decision_note: Mapped[str] = mapped_column(String(800), default="")
    decided_by: Mapped[str] = mapped_column(String(160), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


Base.metadata.create_all(engine)


def session() -> Generator[Session, None, None]:
    db = DB()
    try:
        yield db
    finally:
        db.close()


def cleanup_initial_demo_data() -> None:
    """Remove apenas os registros fictícios usados no primeiro mockup."""
    db = DB()
    try:
        demo_workouts = db.scalars(
            select(Workout).where(Workout.title == "Inferiores — Força e Hipertrofia")
        ).all()
        for workout in demo_workouts:
            db.delete(workout)

        demo_runs = db.scalars(
            select(RunActivity).where(
                RunActivity.title == "Corrida Matinal",
                RunActivity.distance_km == 5.02,
                RunActivity.duration_sec == 1716,
            )
        ).all()
        for run in demo_runs:
            db.delete(run)

        # Modalidades são estrutura do aplicativo, não dados de treino do usuário.
        db.commit()
    finally:
        db.close()


cleanup_initial_demo_data()
app = FastAPI(title="RITMOX", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "app": "RITMOX"}


def workout_payload(w: Workout) -> dict:
    return {
        "id": w.id,
        "modality": w.modality,
        "title": w.title,
        "subtitle": w.subtitle,
        "duration_min": w.duration_min,
        "started": w.started,
        "completed": w.completed,
        "exercises": [
            {
                "id": e.id,
                "name": e.name,
                "muscle": e.muscle,
                "sets_total": e.sets_total,
                "reps": e.reps,
                "load_kg": e.load_kg,
                "sets_done": e.sets_done,
            }
            for e in w.exercises
        ],
    }


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(session)):
    workouts = db.scalars(select(Workout)).all()
    runs = db.scalars(select(RunActivity).order_by(RunActivity.created_at)).all()

    completed_workouts = [w for w in workouts if w.completed]
    total_load = sum(
        e.sets_done * e.load_kg
        for w in workouts
        for e in w.exercises
    )
    total_distance = sum(r.distance_km for r in runs)
    active_seconds = sum(r.duration_sec for r in runs) + sum(
        w.duration_min * 60 for w in completed_workouts
    )

    hours, rem = divmod(active_seconds, 3600)
    minutes = rem // 60
    active_time = f"{hours}h {minutes:02d}min" if hours else f"{minutes} min"

    return {
        "user": {"name": "Júnior"},
        "stats": {
            "workouts": len(completed_workouts),
            "distance_km": round(total_distance, 2),
            "total_load_kg": round(total_load, 1),
            "active_time": active_time,
            "sets_done": sum(e.sets_done for w in workouts for e in w.exercises),
        },
        "weekly": [0] * 12,
        "empty": not workouts and not runs,
    }


@app.get("/api/workouts/current")
def current_workout(db: Session = Depends(session)):
    w = db.scalars(select(Workout).where(Workout.modality == "musculacao").order_by(Workout.id)).first()
    if not w:
        return None
    return workout_payload(w)


@app.post("/api/workouts/{workout_id}/start")
def start_workout(workout_id: int, db: Session = Depends(session)):
    w = db.get(Workout, workout_id)
    if not w:
        raise HTTPException(404, "Treino não encontrado")
    w.started = True
    db.commit()
    return workout_payload(w)


@app.post("/api/exercises/{exercise_id}/complete-set")
def complete_set(exercise_id: int, db: Session = Depends(session)):
    e = db.get(Exercise, exercise_id)
    if not e:
        raise HTTPException(404, "Exercício não encontrado")
    if e.sets_done < e.sets_total:
        e.sets_done += 1
    w = e.workout
    if all(x.sets_done >= x.sets_total for x in w.exercises):
        w.completed = True
    db.commit()
    return {"exercise": {"id": e.id, "sets_done": e.sets_done, "sets_total": e.sets_total}, "workout_completed": w.completed}


@app.post("/api/exercises/{exercise_id}/undo-set")
def undo_set(exercise_id: int, db: Session = Depends(session)):
    e = db.get(Exercise, exercise_id)
    if not e:
        raise HTTPException(404, "Exercício não encontrado")
    e.sets_done = max(0, e.sets_done - 1)
    e.workout.completed = False
    db.commit()
    return {"id": e.id, "sets_done": e.sets_done, "sets_total": e.sets_total}


@app.get("/api/runs/latest")
def latest_run(db: Session = Depends(session)):
    r = db.scalars(select(RunActivity).order_by(RunActivity.created_at.desc())).first()
    if not r:
        return None
    return {
        "id": r.id,
        "title": r.title,
        "distance_km": r.distance_km,
        "duration_sec": r.duration_sec,
        "duration": f"{r.duration_sec // 60}:{r.duration_sec % 60:02d}",
        "avg_pace": r.avg_pace,
        "calories": r.calories,
        "avg_hr": r.avg_hr,
        "elevation_m": r.elevation_m,
        "source": r.source,
        "splits": ["5:28", "5:20", "5:06", "5:03", "4:58"],
    }


class RunIn(BaseModel):
    title: str = Field(default="Corrida", min_length=2, max_length=160)
    distance_km: float = Field(gt=0, le=500)
    duration_sec: int = Field(gt=0)
    avg_pace: str = Field(min_length=3, max_length=16)
    calories: int = Field(default=0, ge=0)
    avg_hr: int = Field(default=0, ge=0)
    elevation_m: int = Field(default=0, ge=0)


@app.post("/api/runs")
def create_run(data: RunIn, db: Session = Depends(session)):
    r = RunActivity(**data.model_dump())
    db.add(r)
    db.commit()
    db.refresh(r)
    return {"id": r.id, "ok": True}


@app.get("/api/modalities")
def modalities(db: Session = Depends(session)):
    return [{"id": m.id, "name": m.name, "icon": m.icon, "active": m.active} for m in db.scalars(select(Modality).order_by(Modality.id)).all()]


class ModalityIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    icon: str = Field(default="●", max_length=16)


@app.post("/api/modalities")
def add_modality(data: ModalityIn, db: Session = Depends(session)):
    exists = db.scalar(select(Modality).where(Modality.name == data.name))
    if exists:
        raise HTTPException(409, "Modalidade já cadastrada")
    m = Modality(name=data.name.strip(), icon=data.icon)
    db.add(m)
    db.commit()
    db.refresh(m)
    return {"id": m.id, "name": m.name, "icon": m.icon, "active": m.active}



class PlannedExerciseIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    muscle: str = Field(default="", max_length=120)
    sets_total: int = Field(default=4, ge=1, le=20)
    reps: str = Field(default="8-10", min_length=1, max_length=30)
    load_kg: float = Field(default=0, ge=0, le=2000)


class PlannedBlockIn(BaseModel):
    kind: str = Field(default="strength", min_length=2, max_length=40)
    name: str = Field(default="", max_length=160)
    detail: str = Field(default="", max_length=160)
    sets_total: int = Field(default=0, ge=0, le=30)
    reps: str = Field(default="", max_length=30)
    load_kg: float = Field(default=0, ge=0, le=2000)
    distance_km: float = Field(default=0, ge=0, le=500)
    duration_min: int = Field(default=0, ge=0, le=600)
    pace_target: str = Field(default="", max_length=30)
    repetitions: int = Field(default=0, ge=0, le=100)
    rest_sec: int = Field(default=0, ge=0, le=3600)
    intensity: str = Field(default="", max_length=40)


class WorkoutPlanIn(BaseModel):
    planned_date: str = Field(min_length=10, max_length=10)
    title: str = Field(min_length=2, max_length=160)
    modality: str = Field(default="musculacao", min_length=2, max_length=40)
    duration_min: int = Field(default=45, ge=5, le=600)
    notes: str = Field(default="", max_length=500)
    exercises: list[PlannedExerciseIn] = Field(default_factory=list)
    blocks: list[PlannedBlockIn] = Field(default_factory=list)

    def parsed_date(self) -> date:
        try:
            return date.fromisoformat(self.planned_date)
        except ValueError as exc:
            raise ValueError("Data inválida. Use AAAA-MM-DD.") from exc


def plan_payload(plan: WorkoutPlan) -> dict:
    return {
        "id": plan.id,
        "planned_date": plan.planned_date,
        "title": plan.title,
        "modality": plan.modality,
        "duration_min": plan.duration_min,
        "notes": plan.notes,
        "exercise_count": len(plan.blocks) if plan.blocks else len(plan.exercises),
        "blocks": [
            {
                "id": b.id,
                "position": b.position,
                "kind": b.kind,
                "name": b.name,
                "detail": b.detail,
                "sets_total": b.sets_total,
                "reps": b.reps,
                "load_kg": b.load_kg,
                "distance_km": b.distance_km,
                "duration_min": b.duration_min,
                "pace_target": b.pace_target,
                "repetitions": b.repetitions,
                "rest_sec": b.rest_sec,
                "intensity": b.intensity,
            }
            for b in plan.blocks
        ],
        "exercises": [
            {
                "id": e.id,
                "position": e.position,
                "name": e.name,
                "muscle": e.muscle,
                "sets_total": e.sets_total,
                "reps": e.reps,
                "load_kg": e.load_kg,
            }
            for e in plan.exercises
        ],
    }


def validate_plan_date(value: str) -> None:
    try:
        date.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, "Data inválida. Use AAAA-MM-DD.")


def ensure_training_planning_allowed(db: Session) -> HealthAssessment:
    assessment = db.scalars(select(HealthAssessment).order_by(HealthAssessment.id.desc())).first()
    if not assessment:
        raise HTTPException(403, "Anamnese obrigatória antes do planejamento de treinos.")
    allowed = assessment.risk_status == "screening_complete" or assessment.professional_clearance
    if not allowed:
        raise HTTPException(403, "Planejamento bloqueado até avaliação e liberação profissional.")
    return assessment


@app.get("/api/training-plans")
def list_training_plans(
    start_date: str,
    end_date: str,
    db: Session = Depends(session),
):
    validate_plan_date(start_date)
    validate_plan_date(end_date)
    if end_date < start_date:
        raise HTTPException(422, "Período inválido.")
    plans = db.scalars(
        select(WorkoutPlan)
        .where(WorkoutPlan.planned_date >= start_date, WorkoutPlan.planned_date <= end_date)
        .order_by(WorkoutPlan.planned_date, WorkoutPlan.id)
    ).all()
    return [plan_payload(p) for p in plans]


@app.get("/api/training-plans/{plan_id}")
def get_training_plan(plan_id: int, db: Session = Depends(session)):
    plan = db.get(WorkoutPlan, plan_id)
    if not plan:
        raise HTTPException(404, "Treino planejado não encontrado")
    return plan_payload(plan)


@app.post("/api/training-plans")
def create_training_plan(data: WorkoutPlanIn, db: Session = Depends(session)):
    ensure_training_planning_allowed(db)
    try:
        data.parsed_date()
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    plan = WorkoutPlan(
        planned_date=data.planned_date,
        title=data.title.strip(),
        modality=data.modality.strip().lower(),
        duration_min=data.duration_min,
        notes=data.notes.strip(),
    )
    plan.exercises = [
        PlannedExercise(
            position=i,
            name=e.name.strip(),
            muscle=e.muscle.strip(),
            sets_total=e.sets_total,
            reps=e.reps.strip(),
            load_kg=e.load_kg,
        )
        for i, e in enumerate(data.exercises)
    ]
    plan.blocks = [
        PlannedBlock(
            position=i,
            kind=b.kind.strip().lower(),
            name=b.name.strip(),
            detail=b.detail.strip(),
            sets_total=b.sets_total,
            reps=b.reps.strip(),
            load_kg=b.load_kg,
            distance_km=b.distance_km,
            duration_min=b.duration_min,
            pace_target=b.pace_target.strip(),
            repetitions=b.repetitions,
            rest_sec=b.rest_sec,
            intensity=b.intensity.strip(),
        )
        for i, b in enumerate(data.blocks)
    ]
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan_payload(plan)


@app.put("/api/training-plans/{plan_id}")
def update_training_plan(plan_id: int, data: WorkoutPlanIn, db: Session = Depends(session)):
    ensure_training_planning_allowed(db)
    plan = db.get(WorkoutPlan, plan_id)
    if not plan:
        raise HTTPException(404, "Treino planejado não encontrado")
    try:
        data.parsed_date()
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    plan.planned_date = data.planned_date
    plan.title = data.title.strip()
    plan.modality = data.modality.strip().lower()
    plan.duration_min = data.duration_min
    plan.notes = data.notes.strip()
    plan.exercises.clear()
    plan.exercises.extend([
        PlannedExercise(
            position=i,
            name=e.name.strip(),
            muscle=e.muscle.strip(),
            sets_total=e.sets_total,
            reps=e.reps.strip(),
            load_kg=e.load_kg,
        )
        for i, e in enumerate(data.exercises)
    ])
    plan.blocks.clear()
    plan.blocks.extend([
        PlannedBlock(
            position=i,
            kind=b.kind.strip().lower(),
            name=b.name.strip(),
            detail=b.detail.strip(),
            sets_total=b.sets_total,
            reps=b.reps.strip(),
            load_kg=b.load_kg,
            distance_km=b.distance_km,
            duration_min=b.duration_min,
            pace_target=b.pace_target.strip(),
            repetitions=b.repetitions,
            rest_sec=b.rest_sec,
            intensity=b.intensity.strip(),
        )
        for i, b in enumerate(data.blocks)
    ])
    db.commit()
    db.refresh(plan)
    return plan_payload(plan)


@app.delete("/api/training-plans/{plan_id}")
def delete_training_plan(plan_id: int, db: Session = Depends(session)):
    plan = db.get(WorkoutPlan, plan_id)
    if not plan:
        raise HTTPException(404, "Treino planejado não encontrado")
    db.delete(plan)
    db.commit()
    return {"ok": True}



class HealthAssessmentIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    birth_date: str = Field(min_length=10, max_length=10)
    sex: str = Field(default="", max_length=40)
    emergency_contact: str = Field(default="", max_length=160)
    emergency_phone: str = Field(default="", max_length=40)
    goal: str = Field(default="", max_length=300)
    current_activity_level: str = Field(default="", max_length=80)
    occupation: str = Field(default="", max_length=120)
    medical_conditions: list[str] = Field(default_factory=list)
    surgeries_injuries: str = Field(default="", max_length=1200)
    medications: str = Field(default="", max_length=1200)
    allergies: str = Field(default="", max_length=800)
    family_history: list[str] = Field(default_factory=list)
    chest_pain: bool = False
    syncope_dizziness: bool = False
    breathlessness_light_activity: bool = False
    palpitations: bool = False
    unexplained_fatigue: bool = False
    edema: bool = False
    musculoskeletal_limitations: bool = False
    pregnant_or_recent_postpartum: bool = False
    smoking: str = Field(default="", max_length=80)
    alcohol: str = Field(default="", max_length=80)
    sleep_hours: float = Field(default=0, ge=0, le=24)
    stress_level: str = Field(default="", max_length=40)
    systolic_bp: int | None = Field(default=None, ge=50, le=300)
    diastolic_bp: int | None = Field(default=None, ge=30, le=200)
    resting_hr: int | None = Field(default=None, ge=20, le=250)
    additional_notes: str = Field(default="", max_length=1500)
    consent_truthful: bool = False
    consent_screening: bool = False


class ProfessionalClearanceIn(BaseModel):
    provider_name: str = Field(min_length=2, max_length=160)
    clearance_date: str = Field(min_length=10, max_length=10)



class ClearanceRequestIn(BaseModel):
    professional_name: str = Field(min_length=2, max_length=160)
    professional_email: str = Field(min_length=5, max_length=220)
    message: str = Field(default="", max_length=800)


class ClearanceDecisionIn(BaseModel):
    approved: bool
    professional_name: str = Field(min_length=2, max_length=160)
    note: str = Field(default="", max_length=800)


def require_professional_key(provided: str | None) -> None:
    expected = os.getenv("PROFESSIONAL_APPROVAL_KEY", "").strip()
    if not expected:
        raise HTTPException(503, "A chave de aprovação profissional ainda não foi configurada.")
    if not provided or provided != expected:
        raise HTTPException(403, "Acesso restrito ao profissional responsável.")


def health_red_flags(data: HealthAssessmentIn) -> list[str]:
    flags: list[str] = []
    symptom_map = {
        "chest_pain": "Dor ou desconforto no peito",
        "syncope_dizziness": "Desmaio ou tontura importante",
        "breathlessness_light_activity": "Falta de ar em repouso ou esforço leve",
        "palpitations": "Palpitações relevantes",
        "unexplained_fatigue": "Fadiga inexplicada",
        "edema": "Inchaço persistente em membros",
        "musculoskeletal_limitations": "Limitação musculoesquelética importante",
        "pregnant_or_recent_postpartum": "Gestação ou pós-parto recente",
    }
    for key, label in symptom_map.items():
        if getattr(data, key):
            flags.append(label)

    high_attention_conditions = {
        "cardiopatia": "Doença cardíaca",
        "hipertensao_nao_controlada": "Hipertensão não controlada",
        "avc": "Histórico de AVC",
        "doenca_renal": "Doença renal",
        "doenca_pulmonar_relevante": "Doença pulmonar relevante",
        "diabetes_com_complicacoes": "Diabetes com complicações",
    }
    selected = set(data.medical_conditions)
    for key, label in high_attention_conditions.items():
        if key in selected:
            flags.append(label)

    if data.systolic_bp is not None and data.systolic_bp >= 180:
        flags.append("Pressão sistólica informada muito elevada")
    if data.diastolic_bp is not None and data.diastolic_bp >= 120:
        flags.append("Pressão diastólica informada muito elevada")

    return flags


def assessment_payload(item: HealthAssessment | None, db: Session | None = None) -> dict | None:
    if not item:
        return None
    data = json.loads(item.payload_json or "{}")
    red_flags = json.loads(item.red_flags_json or "[]")
    allowed = item.risk_status == "screening_complete" or item.professional_clearance
    request = None
    if db is not None:
        request = db.scalars(
            select(ClearanceRequest)
            .where(ClearanceRequest.assessment_id == item.id)
            .order_by(ClearanceRequest.id.desc())
        ).first()
    request_payload = None if not request else {
        "id": request.id,
        "status": request.status,
        "professional_name": request.professional_name,
        "professional_email": request.professional_email,
        "message": request.message,
        "decision_note": request.decision_note,
        "decided_by": request.decided_by,
        "created_at": request.created_at.isoformat() if request.created_at else None,
        "decided_at": request.decided_at.isoformat() if request.decided_at else None,
    }
    return {
        "id": item.id,
        "data": data,
        "risk_status": item.risk_status,
        "red_flags": red_flags,
        "professional_clearance": item.professional_clearance,
        "clearance_provider": item.clearance_provider,
        "clearance_date": item.clearance_date,
        "training_allowed": allowed,
        "clearance_request": request_payload,
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


@app.get("/api/health-assessment/latest")
def latest_health_assessment(db: Session = Depends(session)):
    item = db.scalars(select(HealthAssessment).order_by(HealthAssessment.id.desc())).first()
    return assessment_payload(item, db)


@app.post("/api/health-assessment")
def save_health_assessment(data: HealthAssessmentIn, db: Session = Depends(session)):
    if not data.consent_truthful or not data.consent_screening:
        raise HTTPException(422, "É necessário confirmar as declarações da triagem.")
    try:
        date.fromisoformat(data.birth_date)
    except ValueError:
        raise HTTPException(422, "Data de nascimento inválida.")

    flags = health_red_flags(data)
    status = "attention_required" if flags else "screening_complete"
    item = HealthAssessment(
        payload_json=json.dumps(data.model_dump(), ensure_ascii=False),
        risk_status=status,
        red_flags_json=json.dumps(flags, ensure_ascii=False),
        professional_clearance=False,
        completed_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return assessment_payload(item, db)



@app.get("/api/clearance-requests/latest")
def latest_clearance_request(db: Session = Depends(session)):
    assessment = db.scalars(select(HealthAssessment).order_by(HealthAssessment.id.desc())).first()
    if not assessment:
        return None
    request = db.scalars(
        select(ClearanceRequest)
        .where(ClearanceRequest.assessment_id == assessment.id)
        .order_by(ClearanceRequest.id.desc())
    ).first()
    if not request:
        return None
    return {
        "id": request.id,
        "assessment_id": request.assessment_id,
        "status": request.status,
        "professional_name": request.professional_name,
        "professional_email": request.professional_email,
        "message": request.message,
        "decision_note": request.decision_note,
        "decided_by": request.decided_by,
        "created_at": request.created_at.isoformat() if request.created_at else None,
        "decided_at": request.decided_at.isoformat() if request.decided_at else None,
    }


@app.post("/api/clearance-requests")
def create_clearance_request(data: ClearanceRequestIn, db: Session = Depends(session)):
    assessment = db.scalars(select(HealthAssessment).order_by(HealthAssessment.id.desc())).first()
    if not assessment:
        raise HTTPException(409, "Conclua a anamnese antes de solicitar liberação profissional.")
    if assessment.professional_clearance:
        raise HTTPException(409, "Já existe liberação profissional registrada.")
    if assessment.risk_status != "attention_required":
        raise HTTPException(409, "A triagem atual não exige liberação profissional.")

    existing = db.scalars(
        select(ClearanceRequest)
        .where(
            ClearanceRequest.assessment_id == assessment.id,
            ClearanceRequest.status == "pending",
        )
        .order_by(ClearanceRequest.id.desc())
    ).first()
    if existing:
        return {
            "id": existing.id,
            "status": existing.status,
            "professional_name": existing.professional_name,
            "professional_email": existing.professional_email,
            "message": existing.message,
        }

    request = ClearanceRequest(
        assessment_id=assessment.id,
        professional_name=data.professional_name.strip(),
        professional_email=data.professional_email.strip().lower(),
        message=data.message.strip(),
        status="pending",
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return {
        "id": request.id,
        "status": request.status,
        "professional_name": request.professional_name,
        "professional_email": request.professional_email,
        "message": request.message,
    }


@app.get("/api/professional/clearance-requests")
def professional_clearance_requests(
    x_professional_key: str | None = Header(default=None),
    db: Session = Depends(session),
):
    require_professional_key(x_professional_key)
    requests = db.scalars(
        select(ClearanceRequest)
        .where(ClearanceRequest.status == "pending")
        .order_by(ClearanceRequest.created_at.desc())
    ).all()
    return [
        {
            "id": r.id,
            "assessment_id": r.assessment_id,
            "professional_name": r.professional_name,
            "professional_email": r.professional_email,
            "message": r.message,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in requests
    ]


@app.post("/api/professional/clearance-requests/{request_id}/decision")
def decide_clearance_request(
    request_id: int,
    data: ClearanceDecisionIn,
    x_professional_key: str | None = Header(default=None),
    db: Session = Depends(session),
):
    require_professional_key(x_professional_key)
    request = db.get(ClearanceRequest, request_id)
    if not request:
        raise HTTPException(404, "Solicitação não encontrada.")
    if request.status != "pending":
        raise HTTPException(409, "Esta solicitação já foi analisada.")

    assessment = db.get(HealthAssessment, request.assessment_id)
    if not assessment:
        raise HTTPException(404, "Anamnese vinculada não encontrada.")

    request.status = "approved" if data.approved else "rejected"
    request.decision_note = data.note.strip()
    request.decided_by = data.professional_name.strip()
    request.decided_at = datetime.now(timezone.utc)

    if data.approved:
        assessment.professional_clearance = True
        assessment.clearance_provider = data.professional_name.strip()
        assessment.clearance_date = date.today().isoformat()
        assessment.updated_at = datetime.now(timezone.utc)

    db.commit()
    return {
        "ok": True,
        "status": request.status,
        "training_allowed": assessment.risk_status == "screening_complete" or assessment.professional_clearance,
    }


@app.post("/api/health-assessment/{assessment_id}/clearance", include_in_schema=False)
def register_professional_clearance_disabled(
    assessment_id: int,
    data: ProfessionalClearanceIn,
    db: Session = Depends(session),
):
    raise HTTPException(403, "A liberação deve ser aprovada pelo profissional responsável, não pelo aluno.")


@app.get("/api/integrations/strava")
def strava_status():
    return {
        "configured": bool(os.getenv("STRAVA_CLIENT_ID") and os.getenv("STRAVA_CLIENT_SECRET")),
        "connected": False,
        "message": "Estrutura preparada. OAuth será ativado na etapa de integração.",
    }
