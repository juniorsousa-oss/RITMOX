from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Generator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, create_engine, select
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


class WorkoutPlanIn(BaseModel):
    planned_date: str = Field(min_length=10, max_length=10)
    title: str = Field(min_length=2, max_length=160)
    modality: str = Field(default="musculacao", min_length=2, max_length=40)
    duration_min: int = Field(default=45, ge=5, le=600)
    notes: str = Field(default="", max_length=500)
    exercises: list[PlannedExerciseIn] = Field(default_factory=list)

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
        "exercise_count": len(plan.exercises),
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
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan_payload(plan)


@app.put("/api/training-plans/{plan_id}")
def update_training_plan(plan_id: int, data: WorkoutPlanIn, db: Session = Depends(session)):
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


@app.get("/api/integrations/strava")
def strava_status():
    return {
        "configured": bool(os.getenv("STRAVA_CLIENT_ID") and os.getenv("STRAVA_CLIENT_SECRET")),
        "connected": False,
        "message": "Estrutura preparada. OAuth será ativado na etapa de integração.",
    }
