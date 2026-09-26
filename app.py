from __future__ import annotations

import os
import json
import base64
import html as html_lib
from io import BytesIO
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Generator

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
BUILD_VERSION = "20260926-59"

raw_database_url = os.getenv("DATABASE_URL", "").strip()
require_persistent_db = os.getenv("REQUIRE_PERSISTENT_DB", "").strip().lower() in {"1", "true", "yes", "on"}

if require_persistent_db and not raw_database_url:
    raise RuntimeError(
        "RITMOX: DATABASE_URL é obrigatório em produção. "
        "O aplicativo não iniciará com SQLite efêmero."
    )

database_url = raw_database_url or f"sqlite:///{ROOT / 'ritmox.db'}"
if database_url.startswith("postgres://"):
    database_url = "postgresql+psycopg://" + database_url[len("postgres://"):]
elif database_url.startswith("postgresql://") and "+psycopg" not in database_url:
    database_url = "postgresql+psycopg://" + database_url[len("postgresql://"):]

is_postgres = database_url.startswith("postgresql+psycopg://")
db_schema = os.getenv("DB_SCHEMA", "ritmox").strip() if is_postgres else ""

connect_args: dict[str, Any] = {"check_same_thread": False} if database_url.startswith("sqlite:") else {}
if is_postgres and db_schema:
    # Mantém todas as tabelas do RITMOX isoladas no schema próprio do Supabase.
    connect_args["options"] = f"-csearch_path={db_schema},public"

engine = create_engine(
    database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)
DB = sessionmaker(bind=engine, expire_on_commit=False)

storage_backend = "postgresql" if is_postgres else "sqlite"
storage_persistent = bool(is_postgres)


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



class AnamnesisQuestion(Base):
    __tablename__ = "anamnesis_questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    section: Mapped[str] = mapped_column(String(120), default="Geral")
    label: Mapped[str] = mapped_column(String(500))
    question_type: Mapped[str] = mapped_column(String(40), default="yes_no")
    help_text: Mapped[str] = mapped_column(String(500), default="")
    placeholder: Mapped[str] = mapped_column(String(300), default="")
    options_json: Mapped[str] = mapped_column(Text, default="[]")
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_values_json: Mapped[str] = mapped_column(Text, default="[]")
    risk_message: Mapped[str] = mapped_column(String(500), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AppSetting(Base):
    __tablename__ = "app_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class UserProfile(Base):
    __tablename__ = "user_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), default="Júnior")
    email: Mapped[str] = mapped_column(String(220), default="")
    birth_date: Mapped[str] = mapped_column(String(10), default="")
    goals: Mapped[str] = mapped_column(String(500), default="")
    photo_data: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


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



DEFAULT_ANAMNESIS_QUESTIONS = [
    # 1. Identificação e contexto
    {"section":"Identificação e contexto","label":"Nome completo do aluno","question_type":"text","required":True,"placeholder":"Nome completo"},
    {"section":"Identificação e contexto","label":"Data de nascimento","question_type":"date","required":True},
    {"section":"Identificação e contexto","label":"Sexo / identificação","question_type":"select","options":["Masculino","Feminino","Outro","Prefiro não informar"],"required":False},
    {"section":"Identificação e contexto","label":"Profissão / ocupação principal","question_type":"text","placeholder":"Ex.: administrativo, motorista, estudante","required":False},
    {"section":"Identificação e contexto","label":"Telefone para contato de emergência","question_type":"text","placeholder":"DDD + número","required":True},
    {"section":"Identificação e contexto","label":"Nome do contato de emergência","question_type":"text","required":True},
    {"section":"Identificação e contexto","label":"Qual é seu principal objetivo com o treinamento?","question_type":"multiselect","options":["Saúde geral","Condicionamento cardiorrespiratório","Ganho de força","Hipertrofia","Emagrecimento / composição corporal","Corrida / performance","Mobilidade / flexibilidade","Qualidade de vida","Retorno ao exercício","Outro"],"required":True},
    {"section":"Identificação e contexto","label":"Existe alguma meta, prova, competição ou prazo importante?","question_type":"textarea","placeholder":"Descreva, se houver","required":False},

    # 2. Histórico de atividade física
    {"section":"Histórico de atividade física","label":"Como você classifica seu nível atual de atividade física?","question_type":"select","options":["Sedentário","Pouco ativo","Regularmente ativo","Muito ativo / treinamento estruturado"],"required":True},
    {"section":"Histórico de atividade física","label":"Quantos dias por semana você pratica atividade física atualmente?","question_type":"select","options":["0","1","2","3","4","5","6","7"],"required":True},
    {"section":"Histórico de atividade física","label":"Há quanto tempo você mantém uma rotina regular de exercícios?","question_type":"select","options":["Não mantenho atualmente","Menos de 1 mês","1 a 3 meses","3 a 6 meses","6 a 12 meses","Mais de 1 ano"],"required":True},
    {"section":"Histórico de atividade física","label":"Quais modalidades você pratica ou praticou recentemente?","question_type":"multiselect","options":["Musculação","Corrida","Caminhada","Ciclismo","Natação","Funcional / Cross training","Esportes coletivos","Lutas","Pilates / Yoga","Outra"],"required":False},
    {"section":"Histórico de atividade física","label":"Descreva seu histórico de treinamento, incluindo frequência, duração e intensidade habituais.","question_type":"textarea","required":False,"placeholder":"Ex.: musculação 3x/semana, corrida 2x/semana"},
    {"section":"Histórico de atividade física","label":"Você está retornando ao exercício após período prolongado de inatividade?","question_type":"yes_no","required":True},
    {"section":"Histórico de atividade física","label":"Você já interrompeu exercícios por dor, mal-estar ou orientação profissional?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Histórico de interrupção do exercício por dor, mal-estar ou orientação profissional"},
    {"section":"Histórico de atividade física","label":"Há algum movimento, exercício ou modalidade que você não deseja ou não consegue realizar?","question_type":"textarea","required":False},

    # 3. Sintomas e sinais de alerta
    {"section":"Sintomas e sinais de alerta","label":"Você sente dor, pressão, aperto ou desconforto no peito durante esforço ou em repouso?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Dor, pressão ou desconforto no peito"},
    {"section":"Sintomas e sinais de alerta","label":"Você já teve desmaio, perda de consciência ou tontura importante, especialmente durante esforço?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Desmaio, perda de consciência ou tontura importante"},
    {"section":"Sintomas e sinais de alerta","label":"Você apresenta falta de ar desproporcional, em repouso ou com esforço leve?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Falta de ar desproporcional em repouso ou esforço leve"},
    {"section":"Sintomas e sinais de alerta","label":"Você apresenta palpitações ou batimentos irregulares acompanhados de tontura, dor no peito ou mal-estar?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Palpitações associadas a sintomas"},
    {"section":"Sintomas e sinais de alerta","label":"Você apresenta inchaço persistente e sem causa conhecida em pés, tornozelos ou pernas?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Edema persistente sem causa conhecida"},
    {"section":"Sintomas e sinais de alerta","label":"Você sente dor ou câimbra nas panturrilhas ao caminhar que melhora ao parar?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Dor em panturrilha ao esforço compatível com possível claudicação"},
    {"section":"Sintomas e sinais de alerta","label":"Você apresenta fadiga intensa, fraqueza incomum ou queda recente e inexplicada da tolerância ao esforço?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Fadiga ou redução inexplicada da tolerância ao esforço"},
    {"section":"Sintomas e sinais de alerta","label":"Existe algum sintoma atual que piore com atividade física e ainda não tenha sido avaliado?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Sintoma atual agravado por atividade física sem avaliação profissional"},

    # 4. Histórico cardiovascular, metabólico, renal e respiratório
    {"section":"Histórico clínico","label":"Algum profissional já informou que você possui doença cardíaca, insuficiência cardíaca, arritmia relevante ou outra condição cardiovascular?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Condição cardiovascular conhecida"},
    {"section":"Histórico clínico","label":"Você já teve infarto, angina, cirurgia cardíaca, angioplastia, marca-passo ou outro procedimento cardiovascular?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Histórico de evento ou procedimento cardiovascular"},
    {"section":"Histórico clínico","label":"Você já teve AVC, AIT ou outro evento cerebrovascular?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Histórico de AVC/AIT"},
    {"section":"Histórico clínico","label":"Você possui hipertensão arterial diagnosticada?","question_type":"yes_no","required":True},
    {"section":"Histórico clínico","label":"Sua pressão arterial está atualmente sem controle, ou houve orientação profissional para restringir exercícios por causa da pressão?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Hipertensão não controlada ou restrição profissional relacionada à pressão arterial"},
    {"section":"Histórico clínico","label":"Você possui diabetes mellitus?","question_type":"yes_no","required":True},
    {"section":"Histórico clínico","label":"Seu diabetes apresenta complicações, episódios frequentes de hipoglicemia ou orientação específica para exercício?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Diabetes com complicações, hipoglicemia recorrente ou necessidade de orientação específica"},
    {"section":"Histórico clínico","label":"Você possui doença renal crônica ou está em acompanhamento por alteração importante da função renal?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Doença renal crônica ou alteração renal relevante"},
    {"section":"Histórico clínico","label":"Você possui asma, DPOC ou outra doença respiratória?","question_type":"yes_no","required":True},
    {"section":"Histórico clínico","label":"Sua condição respiratória está descontrolada, com crises recentes ou limitação importante ao esforço?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Condição respiratória descontrolada ou limitante"},
    {"section":"Histórico clínico","label":"Você possui outra doença crônica, neurológica, autoimune, infecciosa ou condição clínica relevante para o exercício?","question_type":"textarea","required":False,"placeholder":"Informe diagnóstico e situação atual"},

    # 5. Musculoesquelético e neurológico
    {"section":"Sistema musculoesquelético e neurológico","label":"Você sente dor musculoesquelética atualmente?","question_type":"yes_no","required":True},
    {"section":"Sistema musculoesquelético e neurológico","label":"Existe lesão, dor ou limitação que impeça ou modifique movimentos do dia a dia ou do exercício?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Lesão, dor ou limitação funcional que interfere no exercício"},
    {"section":"Sistema musculoesquelético e neurológico","label":"Descreva lesões atuais ou anteriores relevantes.","question_type":"textarea","required":False,"placeholder":"Local, diagnóstico, quando ocorreu e situação atual"},
    {"section":"Sistema musculoesquelético e neurológico","label":"Você já realizou cirurgia ortopédica, neurológica ou de coluna?","question_type":"yes_no","required":True},
    {"section":"Sistema musculoesquelético e neurológico","label":"Descreva cirurgias anteriores relevantes e possíveis restrições.","question_type":"textarea","required":False},
    {"section":"Sistema musculoesquelético e neurológico","label":"Você apresenta perda de equilíbrio, quedas recorrentes, fraqueza neurológica ou alteração importante de coordenação?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Alteração de equilíbrio, quedas recorrentes ou déficit neurológico relevante"},
    {"section":"Sistema musculoesquelético e neurológico","label":"Você possui osteoporose, fratura por fragilidade ou alto risco conhecido de fratura?","question_type":"yes_no","required":True},
    {"section":"Sistema musculoesquelético e neurológico","label":"Você possui epilepsia ou histórico de convulsões?","question_type":"yes_no","required":True},
    {"section":"Sistema musculoesquelético e neurológico","label":"Houve convulsão recente, alteração no controle da epilepsia ou orientação para restrição de exercício?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Convulsão recente ou epilepsia sem controle adequado para atividade física"},

    # 6. Medicamentos, alergias e acompanhamento
    {"section":"Medicamentos e acompanhamento","label":"Você utiliza medicamentos de uso contínuo?","question_type":"yes_no","required":True},
    {"section":"Medicamentos e acompanhamento","label":"Informe os medicamentos em uso e, se souber, a finalidade.","question_type":"textarea","required":False,"placeholder":"Nome, dose e finalidade"},
    {"section":"Medicamentos e acompanhamento","label":"Algum medicamento já provocou tontura, queda de pressão, alteração de frequência cardíaca ou hipoglicemia durante atividade?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Efeito de medicamento com potencial impacto durante exercício"},
    {"section":"Medicamentos e acompanhamento","label":"Você possui alergia importante, inclusive a medicamentos?","question_type":"yes_no","required":True},
    {"section":"Medicamentos e acompanhamento","label":"Descreva alergias relevantes e condutas de emergência, se houver.","question_type":"textarea","required":False},
    {"section":"Medicamentos e acompanhamento","label":"Algum profissional de saúde já recomendou que você faça exercícios somente com supervisão ou após avaliação específica?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Orientação profissional prévia para supervisão ou avaliação antes do exercício"},

    # 7. Histórico familiar
    {"section":"Histórico familiar","label":"Pai, mãe ou irmão(ã) teve infarto, morte súbita ou doença cardiovascular em idade precoce?","question_type":"yes_no","required":True},
    {"section":"Histórico familiar","label":"Existe histórico familiar de morte súbita inexplicada, cardiomiopatia ou arritmia hereditária?","question_type":"yes_no","required":True,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Histórico familiar de morte súbita ou doença cardíaca hereditária"},
    {"section":"Histórico familiar","label":"Existe histórico familiar relevante de hipertensão, diabetes, AVC ou doença renal?","question_type":"multiselect","options":["Hipertensão","Diabetes","AVC","Doença renal","Nenhum conhecido"],"required":False},

    # 8. Hábitos e recuperação
    {"section":"Hábitos, sono e recuperação","label":"Você fuma atualmente?","question_type":"select","options":["Não","Sim","Ex-fumante"],"required":True},
    {"section":"Hábitos, sono e recuperação","label":"Com que frequência consome bebidas alcoólicas?","question_type":"select","options":["Não consumo","Ocasionalmente","1 a 2 dias por semana","3 ou mais dias por semana"],"required":True},
    {"section":"Hábitos, sono e recuperação","label":"Quantas horas você dorme, em média, por noite?","question_type":"number","required":False,"placeholder":"Ex.: 7.5"},
    {"section":"Hábitos, sono e recuperação","label":"Como você avalia a qualidade do seu sono?","question_type":"select","options":["Muito boa","Boa","Regular","Ruim","Muito ruim"],"required":True},
    {"section":"Hábitos, sono e recuperação","label":"Como você avalia seu nível atual de estresse?","question_type":"select","options":["Baixo","Moderado","Alto","Muito alto"],"required":True},
    {"section":"Hábitos, sono e recuperação","label":"Sua rotina de trabalho envolve esforço físico intenso, longos períodos em pé, trabalho noturno ou movimentos repetitivos?","question_type":"textarea","required":False},
    {"section":"Hábitos, sono e recuperação","label":"Existe alguma questão de alimentação, relação com comida ou peso que você considere importante para o planejamento do treino?","question_type":"textarea","required":False},

    # 9. Gestação e situações especiais
    {"section":"Situações especiais","label":"Você está gestante ou em período pós-parto?","question_type":"select","options":["Não","Gestante","Pós-parto até 12 semanas","Pós-parto há mais de 12 semanas","Não se aplica / prefiro não informar"],"required":False},
    {"section":"Situações especiais","label":"Em caso de gestação ou pós-parto, existe complicação, sintoma ou orientação profissional para restringir atividade física?","question_type":"yes_no","required":False,"risk_enabled":True,"risk_values":["Sim"],"risk_message":"Gestação/pós-parto com complicação, sintoma ou restrição profissional"},
    {"section":"Situações especiais","label":"Você possui deficiência ou condição funcional que exija adaptação específica do treinamento?","question_type":"yes_no","required":True},
    {"section":"Situações especiais","label":"Descreva adaptações de acessibilidade, comunicação ou execução que devam ser consideradas.","question_type":"textarea","required":False},

    # 10. Medidas e exames recentes
    {"section":"Medidas e informações recentes","label":"Altura (cm), se souber","question_type":"number","required":False,"placeholder":"Ex.: 175"},
    {"section":"Medidas e informações recentes","label":"Peso corporal atual (kg), se desejar informar","question_type":"number","required":False,"placeholder":"Ex.: 75.5"},
    {"section":"Medidas e informações recentes","label":"Pressão arterial sistólica mais recente, se disponível (mmHg)","question_type":"number","required":False,"placeholder":"Ex.: 120"},
    {"section":"Medidas e informações recentes","label":"Pressão arterial diastólica mais recente, se disponível (mmHg)","question_type":"number","required":False,"placeholder":"Ex.: 80"},
    {"section":"Medidas e informações recentes","label":"Frequência cardíaca de repouso mais recente, se disponível (bpm)","question_type":"number","required":False,"placeholder":"Ex.: 65"},
    {"section":"Medidas e informações recentes","label":"Existe exame, laudo ou recomendação profissional recente que deva ser considerado no treinamento?","question_type":"textarea","required":False,"placeholder":"Descreva ou informe onde está registrado"},

    # 11. Preferências e segurança
    {"section":"Preferências e segurança","label":"Quais dias da semana você normalmente consegue treinar?","question_type":"multiselect","options":["Segunda","Terça","Quarta","Quinta","Sexta","Sábado","Domingo"],"required":False},
    {"section":"Preferências e segurança","label":"Quanto tempo você normalmente tem disponível por sessão?","question_type":"select","options":["Até 30 min","30 a 45 min","45 a 60 min","60 a 90 min","Mais de 90 min"],"required":False},
    {"section":"Preferências e segurança","label":"Qual ambiente você utilizará com maior frequência?","question_type":"multiselect","options":["Academia","Casa","Rua / parque","Pista","Esteira","Bicicleta / rolo","Outro"],"required":False},
    {"section":"Preferências e segurança","label":"Há qualquer outra informação que o profissional responsável deva saber antes de prescrever seu treinamento?","question_type":"textarea","required":False},
]


def _insert_default_anamnesis(db: Session, replace: bool = False) -> int:
    if replace:
        for item in db.scalars(select(AnamnesisQuestion)).all():
            db.delete(item)
        db.flush()

    count = 0
    for index, item in enumerate(DEFAULT_ANAMNESIS_QUESTIONS, start=1):
        q = AnamnesisQuestion(
            section=item["section"],
            label=item["label"],
            question_type=item.get("question_type", "yes_no"),
            help_text=item.get("help_text", ""),
            placeholder=item.get("placeholder", ""),
            options_json=json.dumps(item.get("options", []), ensure_ascii=False),
            required=item.get("required", False),
            risk_enabled=item.get("risk_enabled", False),
            risk_values_json=json.dumps(item.get("risk_values", []), ensure_ascii=False),
            risk_message=item.get("risk_message", ""),
            active=True,
            position=index * 10,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(q)
        count += 1
    return count


def seed_default_anamnesis_once() -> None:
    db = DB()
    try:
        seeded = db.scalar(select(AppSetting).where(AppSetting.key == "default_anamnesis_seeded"))
        if seeded:
            return

        existing = db.scalars(select(AnamnesisQuestion).order_by(AnamnesisQuestion.id)).all()
        if not existing:
            _insert_default_anamnesis(db)

        db.add(AppSetting(
            key="default_anamnesis_seeded",
            value="1",
            updated_at=datetime.now(timezone.utc),
        ))
        db.commit()
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


# Nunca execute limpeza destrutiva automaticamente em produção.
# Dados de demonstração só podem ser removidos explicitamente em ambiente local.
if os.getenv("RITMOX_CLEANUP_DEMO_DATA", "").strip().lower() in {"1", "true", "yes", "on"}:
    cleanup_initial_demo_data()

seed_default_anamnesis_once()
app = FastAPI(title="RITMOX", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(
        STATIC / "index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


def health_payload():
    return {
        "status": "ok",
        "app": "RITMOX",
        "build": BUILD_VERSION,
        "storage": {
            "backend": storage_backend,
            "persistent": storage_persistent,
            "schema": db_schema or None,
        },
    }


@app.get("/health")
def health():
    return health_payload()


@app.get("/saude", include_in_schema=False)
def health_saude():
    return health_payload()


@app.get("/Saúde", include_in_schema=False)
def health_saude_render():
    return health_payload()


@app.get("/api/version", include_in_schema=False)
def app_version():
    return {"app": "RITMOX", "build": BUILD_VERSION}


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


class TrainingProgramApplyIn(BaseModel):
    method_key: str = Field(min_length=2, max_length=40)
    start_date: str = Field(min_length=10, max_length=10)
    weeks: int = Field(default=4, ge=1, le=12)

    def parsed_start(self) -> date:
        try:
            return date.fromisoformat(self.start_date)
        except ValueError as exc:
            raise ValueError("Data inválida. Use AAAA-MM-DD.") from exc


TRAINING_METHODS: dict[str, dict[str, Any]] = {
    "hypertrophy": {
        "key": "hypertrophy",
        "title": "Hipertrofia",
        "tag": "Força progressiva",
        "summary": "Volume semanal progressivo para ganho de massa muscular.",
        "modality": "Musculação + Corrida leve",
        "goal": "Hipertrofia",
        "frequency": "4x musculação + 2x cardio leve",
        "structure": "A/B + corrida regenerativa",
        "description": "Prioriza consistência e volume semanal. A referência ACSM 2026 aponta maior volume semanal, em torno de 10 séries por grupo muscular, como estratégia útil para hipertrofia.",
        "evidence": "ACSM 2026",
        "sessions": [
            {"day": 0, "title": "Musculação A", "modality": "musculacao", "duration": 60, "detail": "Peito, costas, ombros e braços", "blocks": [
                ("Supino horizontal", "Peito", 3, "6-12"), ("Remada horizontal", "Costas", 3, "6-12"),
                ("Desenvolvimento", "Ombros", 3, "6-12"), ("Puxada vertical", "Costas", 3, "6-12"),
                ("Braços", "Bíceps / Tríceps", 2, "8-15"),
            ]},
            {"day": 1, "title": "Musculação B", "modality": "musculacao", "duration": 60, "detail": "Membros inferiores e core", "blocks": [
                ("Agachamento", "Quadríceps / Glúteos", 3, "6-12"), ("Levantamento romeno", "Posteriores", 3, "6-12"),
                ("Afundo", "Quadríceps / Glúteos", 3, "8-12"), ("Panturrilha", "Panturrilhas", 3, "10-15"),
                ("Core", "Abdômen / estabilizadores", 3, "10-15"),
            ]},
            {"day": 2, "title": "Corrida regenerativa", "modality": "corrida", "duration": 25, "detail": "Zona 2 / leve", "run": ("run_recovery", 25, "Z2")},
            {"day": 3, "title": "Musculação A", "modality": "musculacao", "duration": 60, "detail": "Peito, costas, ombros e braços", "blocks": [
                ("Supino inclinado", "Peito", 3, "6-12"), ("Remada unilateral", "Costas", 3, "6-12"),
                ("Elevação lateral", "Ombros", 3, "10-15"), ("Puxada vertical", "Costas", 3, "6-12"),
                ("Braços", "Bíceps / Tríceps", 2, "8-15"),
            ]},
            {"day": 4, "title": "Musculação B", "modality": "musculacao", "duration": 60, "detail": "Membros inferiores e core", "blocks": [
                ("Leg press", "Quadríceps / Glúteos", 3, "8-12"), ("Flexão de joelhos", "Posteriores", 3, "8-12"),
                ("Extensão de joelhos", "Quadríceps", 3, "10-15"), ("Panturrilha", "Panturrilhas", 3, "10-15"),
                ("Core", "Abdômen / estabilizadores", 3, "10-15"),
            ]},
            {"day": 5, "title": "Corrida leve", "modality": "corrida", "duration": 30, "detail": "Zona 2 / conversa confortável", "run": ("run_easy", 30, "Z2")},
        ],
    },
    "strength": {
        "key": "strength",
        "title": "Força",
        "tag": "Carga alta",
        "summary": "Baixas repetições, descanso maior e progressão de carga.",
        "modality": "Musculação",
        "goal": "Aumento de força",
        "frequency": "3x musculação + recuperação",
        "structure": "Corpo inteiro A/B",
        "description": "A referência ACSM 2026 favorece cargas mais altas, em torno de 80% de 1RM, com 2–3 séries por exercício para maximizar força em adultos saudáveis.",
        "evidence": "ACSM 2026",
        "sessions": [
            {"day": 0, "title": "Força A", "modality": "musculacao", "duration": 65, "detail": "Corpo inteiro — ênfase agachamento e supino", "blocks": [
                ("Agachamento", "Membros inferiores", 3, "3-6"), ("Supino", "Peito / tríceps", 3, "3-6"), ("Remada", "Costas", 3, "4-6"),
            ]},
            {"day": 2, "title": "Força B", "modality": "musculacao", "duration": 65, "detail": "Corpo inteiro — ênfase posterior e ombros", "blocks": [
                ("Levantamento terra / variação", "Posteriores / costas", 2, "3-5"), ("Desenvolvimento", "Ombros", 3, "3-6"), ("Puxada / barra", "Costas", 3, "4-6"),
            ]},
            {"day": 4, "title": "Força A", "modality": "musculacao", "duration": 65, "detail": "Corpo inteiro — progressão técnica", "blocks": [
                ("Agachamento / variação", "Membros inferiores", 3, "3-6"), ("Supino / variação", "Peito / tríceps", 3, "3-6"), ("Remada", "Costas", 3, "4-6"),
            ]},
            {"day": 5, "title": "Mobilidade e recuperação", "modality": "mobilidade", "duration": 20, "detail": "Mobilidade ativa e recuperação"},
        ],
    },
    "weight_loss": {
        "key": "weight_loss",
        "title": "Perda de peso",
        "tag": "Cardio + força",
        "summary": "Combina musculação e aeróbio para apoiar controle de peso e preservar massa magra.",
        "modality": "Musculação + Aeróbio",
        "goal": "Redução de gordura corporal",
        "frequency": "3x força + 2x cardio",
        "structure": "Força total + aeróbio progressivo",
        "description": "O consenso ACSM sobre peso corporal enfatiza atividade física dentro de uma estratégia de balanço energético. A musculação ajuda a preservar massa magra e o aeróbio amplia o gasto energético.",
        "evidence": "ACSM 2024 + WHO 2020",
        "sessions": [
            {"day": 0, "title": "Força A", "modality": "musculacao", "duration": 50, "detail": "Corpo inteiro", "blocks": [
                ("Agachamento", "Membros inferiores", 3, "8-12"), ("Supino / flexão", "Peito", 3, "8-12"), ("Remada", "Costas", 3, "8-12"), ("Core", "Core", 3, "10-15"),
            ]},
            {"day": 1, "title": "Cardio moderado", "modality": "corrida", "duration": 40, "detail": "Ritmo confortável", "run": ("run_easy", 40, "Z2")},
            {"day": 3, "title": "Força B", "modality": "musculacao", "duration": 50, "detail": "Corpo inteiro", "blocks": [
                ("Levantamento romeno", "Posteriores", 3, "8-12"), ("Desenvolvimento", "Ombros", 3, "8-12"), ("Puxada", "Costas", 3, "8-12"), ("Core", "Core", 3, "10-15"),
            ]},
            {"day": 4, "title": "Cardio intervalado controlado", "modality": "corrida", "duration": 25, "detail": "Intervalos curtos com recuperação", "run": ("run_interval", 25, "Z3-Z4")},
            {"day": 5, "title": "Força total", "modality": "musculacao", "duration": 45, "detail": "Circuito de força sem pressa", "blocks": [
                ("Agachar", "Membros inferiores", 3, "8-12"), ("Empurrar", "Peito / ombros", 3, "8-12"), ("Puxar", "Costas", 3, "8-12"), ("Carregar / core", "Core", 3, "10-15"),
            ]},
        ],
    },
    "conditioning": {
        "key": "conditioning",
        "title": "Condicionamento",
        "tag": "Base + intervalos",
        "summary": "Combina volume aeróbio moderado com intervalos e força.",
        "modality": "Corrida + Musculação",
        "goal": "Condicionamento cardiorrespiratório",
        "frequency": "3x cardio + 1x força",
        "structure": "Base leve + limiar + intervalos",
        "description": "A WHO recomenda volume aeróbio semanal e fortalecimento; evidências revisadas pelo ACSM mostram que HIIT pode complementar o treino contínuo, desde que a progressão e a recuperação sejam adequadas.",
        "evidence": "WHO 2020 + ACSM 2019",
        "sessions": [
            {"day": 0, "title": "Base aeróbia", "modality": "corrida", "duration": 40, "detail": "Zona 2 / leve", "run": ("run_easy", 40, "Z2")},
            {"day": 2, "title": "Intervalado", "modality": "corrida", "duration": 30, "detail": "Blocos intensos com recuperação", "run": ("run_interval", 30, "Z4")},
            {"day": 4, "title": "Força de suporte", "modality": "musculacao", "duration": 45, "detail": "Corpo inteiro", "blocks": [
                ("Agachamento", "Membros inferiores", 3, "6-10"), ("Empurrar", "Peito / ombros", 3, "6-10"), ("Puxar", "Costas", 3, "6-10"), ("Core", "Core", 3, "10-15"),
            ]},
            {"day": 5, "title": "Tempo / limiar", "modality": "corrida", "duration": 35, "detail": "Ritmo sustentado controlado", "run": ("run_tempo", 35, "Z3-Z4")},
        ],
    },
}


def training_method_payload(method: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in method.items() if k != "sessions"}


def active_training_program(db: Session) -> dict[str, Any] | None:
    row = db.scalar(select(AppSetting).where(AppSetting.key == "active_training_program"))
    if not row or not row.value:
        return None
    try:
        data = json.loads(row.value)
    except (TypeError, json.JSONDecodeError):
        return None
    method = TRAINING_METHODS.get(data.get("method_key", ""))
    if method:
        data["method"] = training_method_payload(method)
    return data


def save_active_training_program(db: Session, data: dict[str, Any]) -> None:
    row = db.scalar(select(AppSetting).where(AppSetting.key == "active_training_program"))
    value = json.dumps(data, ensure_ascii=False)
    now = datetime.now(timezone.utc)
    if row:
        row.value = value
        row.updated_at = now
    else:
        db.add(AppSetting(key="active_training_program", value=value, updated_at=now))


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


@app.get("/api/training-methods")
def list_training_methods():
    return [training_method_payload(method) for method in TRAINING_METHODS.values()]


@app.get("/api/training-program/current")
def current_training_program(db: Session = Depends(session)):
    return {"program": active_training_program(db)}


@app.post("/api/training-program/apply")
def apply_training_program(data: TrainingProgramApplyIn, db: Session = Depends(session)):
    ensure_training_planning_allowed(db)
    method = TRAINING_METHODS.get(data.method_key)
    if not method:
        raise HTTPException(422, "Método de treinamento não reconhecido.")
    try:
        start = data.parsed_start()
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    # Remove somente sessões futuras geradas automaticamente pelo próprio RITMOX.
    # Treinos manuais e histórico anterior são preservados.
    generated = db.scalars(
        select(WorkoutPlan).where(
            WorkoutPlan.planned_date >= data.start_date,
            WorkoutPlan.notes.like("RITMOX_METHOD:%"),
        )
    ).all()
    for plan in generated:
        db.delete(plan)
    db.flush()

    created: list[WorkoutPlan] = []
    for week in range(data.weeks):
        week_start = start + timedelta(days=week * 7)
        for session_template in method["sessions"]:
            planned = week_start + timedelta(days=int(session_template["day"]))
            note = (
                f"RITMOX_METHOD:{data.method_key} · {method['title']} · "
                f"{session_template.get('detail', '')}"
            )[:500]
            plan = WorkoutPlan(
                planned_date=planned.isoformat(),
                title=session_template["title"],
                modality=session_template["modality"],
                duration_min=int(session_template["duration"]),
                notes=note,
            )

            for index, block in enumerate(session_template.get("blocks", [])):
                name, detail, sets_total, reps = block
                plan.blocks.append(PlannedBlock(
                    position=index,
                    kind="strength",
                    name=name,
                    detail=detail,
                    sets_total=sets_total,
                    reps=reps,
                    load_kg=0,
                    distance_km=0,
                    duration_min=0,
                    pace_target="",
                    repetitions=0,
                    rest_sec=0,
                    intensity="",
                ))

            run_data = session_template.get("run")
            if run_data:
                kind, duration_min, intensity = run_data
                plan.blocks.append(PlannedBlock(
                    position=0,
                    kind=kind,
                    name=session_template["title"],
                    detail=session_template.get("detail", ""),
                    sets_total=0,
                    reps="",
                    load_kg=0,
                    distance_km=0,
                    duration_min=int(duration_min),
                    pace_target="",
                    repetitions=0,
                    rest_sec=0,
                    intensity=intensity,
                ))
            db.add(plan)
            created.append(plan)

    program = {
        "method_key": data.method_key,
        "start_date": data.start_date,
        "weeks": data.weeks,
        "title": method["title"],
        "goal": method["goal"],
        "frequency": method["frequency"],
        "structure": method["structure"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    save_active_training_program(db, program)
    db.commit()

    return {
        "program": {**program, "method": training_method_payload(method)},
        "created_count": len(created),
    }


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




class AnamnesisQuestionIn(BaseModel):
    section: str = Field(default="Geral", min_length=1, max_length=120)
    label: str = Field(min_length=2, max_length=500)
    question_type: str = Field(default="yes_no", min_length=2, max_length=40)
    help_text: str = Field(default="", max_length=500)
    placeholder: str = Field(default="", max_length=300)
    options: list[str] = Field(default_factory=list)
    required: bool = False
    risk_enabled: bool = False
    risk_values: list[str] = Field(default_factory=list)
    risk_message: str = Field(default="", max_length=500)
    active: bool = True
    position: int = Field(default=0, ge=0, le=10000)


class UserProfileIn(BaseModel):
    name: str = Field(default="Júnior", min_length=2, max_length=160)
    email: str = Field(default="", max_length=220)
    birth_date: str = Field(default="", max_length=10)
    goals: str = Field(default="", max_length=500)
    photo_data: str = Field(default="", max_length=800000)


class DynamicHealthAssessmentIn(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)
    consent_truthful: bool = False
    consent_screening: bool = False
    signature_requested: bool = False
    signature_name: str = Field(default="", max_length=160)
    signature_data: str = Field(default="", max_length=500000)
    signature_confirmed: bool = False


class AssessmentSignatureIn(BaseModel):
    signer_name: str = Field(min_length=2, max_length=160)
    accepted: bool = False


def question_payload(q: AnamnesisQuestion) -> dict:
    return {
        "id": q.id,
        "section": q.section,
        "label": q.label,
        "question_type": q.question_type,
        "help_text": q.help_text,
        "placeholder": q.placeholder,
        "options": json.loads(q.options_json or "[]"),
        "required": q.required,
        "risk_enabled": q.risk_enabled,
        "risk_values": json.loads(q.risk_values_json or "[]"),
        "risk_message": q.risk_message,
        "active": q.active,
        "position": q.position,
    }


def normalized_answer(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, bool):
        return ["sim" if value else "nao"]
    if isinstance(value, list):
        return [str(v).strip().lower() for v in value if str(v).strip()]
    return [str(value).strip().lower()] if str(value).strip() else []


def answer_triggers_risk(q: AnamnesisQuestion, value: Any) -> bool:
    if not q.risk_enabled:
        return False
    answers = normalized_answer(value)
    if not answers:
        return False
    configured = [str(v).strip().lower() for v in json.loads(q.risk_values_json or "[]") if str(v).strip()]
    if q.question_type == "yes_no" and not configured:
        configured = ["sim"]
    return bool(set(answers) & set(configured))


@app.get("/api/settings/anamnesis/questions")
def list_anamnesis_questions(db: Session = Depends(session)):
    items = db.scalars(
        select(AnamnesisQuestion).order_by(AnamnesisQuestion.position, AnamnesisQuestion.id)
    ).all()
    return [question_payload(q) for q in items]


@app.get("/api/anamnesis/form")
def anamnesis_form(db: Session = Depends(session)):
    items = db.scalars(
        select(AnamnesisQuestion)
        .where(AnamnesisQuestion.active == True)
        .order_by(AnamnesisQuestion.position, AnamnesisQuestion.id)
    ).all()
    return {
        "configured": bool(items),
        "questions": [question_payload(q) for q in items],
    }


@app.post("/api/settings/anamnesis/questions")
def create_anamnesis_question(data: AnamnesisQuestionIn, db: Session = Depends(session)):
    allowed = {"yes_no", "text", "textarea", "number", "date", "select", "multiselect"}
    if data.question_type not in allowed:
        raise HTTPException(422, "Tipo de pergunta inválido.")
    if data.question_type in {"select", "multiselect"} and not data.options:
        raise HTTPException(422, "Informe pelo menos uma opção para perguntas de seleção.")
    if data.position == 0:
        last = db.scalars(select(AnamnesisQuestion).order_by(AnamnesisQuestion.position.desc())).first()
        position = (last.position + 10) if last else 10
    else:
        position = data.position
    item = AnamnesisQuestion(
        section=data.section.strip(),
        label=data.label.strip(),
        question_type=data.question_type,
        help_text=data.help_text.strip(),
        placeholder=data.placeholder.strip(),
        options_json=json.dumps([x.strip() for x in data.options if x.strip()], ensure_ascii=False),
        required=data.required,
        risk_enabled=data.risk_enabled,
        risk_values_json=json.dumps([x.strip() for x in data.risk_values if x.strip()], ensure_ascii=False),
        risk_message=data.risk_message.strip(),
        active=data.active,
        position=position,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return question_payload(item)


@app.put("/api/settings/anamnesis/questions/{question_id}")
def update_anamnesis_question(question_id: int, data: AnamnesisQuestionIn, db: Session = Depends(session)):
    item = db.get(AnamnesisQuestion, question_id)
    if not item:
        raise HTTPException(404, "Pergunta não encontrada.")
    allowed = {"yes_no", "text", "textarea", "number", "date", "select", "multiselect"}
    if data.question_type not in allowed:
        raise HTTPException(422, "Tipo de pergunta inválido.")
    if data.question_type in {"select", "multiselect"} and not data.options:
        raise HTTPException(422, "Informe pelo menos uma opção para perguntas de seleção.")
    item.section = data.section.strip()
    item.label = data.label.strip()
    item.question_type = data.question_type
    item.help_text = data.help_text.strip()
    item.placeholder = data.placeholder.strip()
    item.options_json = json.dumps([x.strip() for x in data.options if x.strip()], ensure_ascii=False)
    item.required = data.required
    item.risk_enabled = data.risk_enabled
    item.risk_values_json = json.dumps([x.strip() for x in data.risk_values if x.strip()], ensure_ascii=False)
    item.risk_message = data.risk_message.strip()
    item.active = data.active
    item.position = data.position
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return question_payload(item)


@app.delete("/api/settings/anamnesis/questions/{question_id}")
def delete_anamnesis_question(question_id: int, db: Session = Depends(session)):
    item = db.get(AnamnesisQuestion, question_id)
    if not item:
        raise HTTPException(404, "Pergunta não encontrada.")
    db.delete(item)
    db.commit()
    return {"ok": True}



@app.post("/api/settings/anamnesis/restore-default")
def restore_default_anamnesis(db: Session = Depends(session)):
    count = _insert_default_anamnesis(db, replace=True)
    seeded = db.scalar(select(AppSetting).where(AppSetting.key == "default_anamnesis_seeded"))
    if seeded:
        seeded.value = "1"
        seeded.updated_at = datetime.now(timezone.utc)
    else:
        db.add(AppSetting(key="default_anamnesis_seeded", value="1", updated_at=datetime.now(timezone.utc)))
    db.commit()
    return {"ok": True, "count": count}


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
    signature_requested = bool(data.get("signature_requested", False))
    signature = data.get("signature") if isinstance(data.get("signature"), dict) else None
    signature_status = "signed" if signature else ("pending" if signature_requested else "not_requested")
    public_data = dict(data)
    if isinstance(public_data.get("signature"), dict):
        public_data["signature"] = {k: v for k, v in public_data["signature"].items() if k != "image_data"}
    public_signature = None if not signature else {k: v for k, v in signature.items() if k != "image_data"}
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
        "data": public_data,
        "risk_status": item.risk_status,
        "red_flags": red_flags,
        "professional_clearance": item.professional_clearance,
        "clearance_provider": item.clearance_provider,
        "clearance_date": item.clearance_date,
        "training_allowed": allowed,
        "signature_requested": signature_requested,
        "signature_status": signature_status,
        "signature": public_signature,
        "clearance_request": request_payload,
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


@app.get("/api/health-assessment/latest")
def latest_health_assessment(db: Session = Depends(session)):
    item = db.scalars(select(HealthAssessment).order_by(HealthAssessment.id.desc())).first()
    return assessment_payload(item, db)


@app.post("/api/health-assessment")
def save_health_assessment(data: DynamicHealthAssessmentIn, db: Session = Depends(session)):
    if not data.consent_truthful or not data.consent_screening:
        raise HTTPException(422, "Confirme as duas declarações antes de concluir a anamnese.")
    if not data.signature_confirmed:
        raise HTTPException(422, "Confirme a assinatura eletrônica do aluno antes de salvar.")
    if len(data.signature_name.strip()) < 2:
        raise HTTPException(422, "Informe o nome do aluno responsável pela assinatura.")
    if not data.signature_data.startswith("data:image/png;base64,"):
        raise HTTPException(422, "A assinatura do aluno é obrigatória antes de salvar.")
    try:
        signature_raw = base64.b64decode(data.signature_data.split(",", 1)[1], validate=True)
    except Exception as exc:
        raise HTTPException(422, "A assinatura informada é inválida. Limpe e assine novamente.") from exc
    if len(signature_raw) < 150:
        raise HTTPException(422, "A assinatura está vazia. Assine no campo indicado antes de salvar.")

    questions = db.scalars(
        select(AnamnesisQuestion)
        .where(AnamnesisQuestion.active == True)
        .order_by(AnamnesisQuestion.position, AnamnesisQuestion.id)
    ).all()
    if not questions:
        raise HTTPException(409, "A anamnese ainda não foi parametrizada em Configurações.")

    missing: list[str] = []
    flags: list[str] = []
    for q in questions:
        key = str(q.id)
        value = data.answers.get(key)
        empty = value is None or value == "" or value == []
        if q.required and empty:
            missing.append(q.label)
        if answer_triggers_risk(q, value):
            flags.append(q.risk_message.strip() or q.label)

    if missing:
        suffix = "; ".join(missing[:5])
        if len(missing) > 5:
            suffix += f"; e mais {len(missing)-5}"
        raise HTTPException(422, "Existem respostas obrigatórias pendentes: " + suffix)

    now = datetime.now(timezone.utc)
    status = "attention_required" if flags else "screening_complete"
    payload = {
        "answers": data.answers,
        "consent_truthful": data.consent_truthful,
        "consent_screening": data.consent_screening,
        "signature_requested": False,
        "signature": {
            "signer_name": data.signature_name.strip(),
            "signed_at": now.isoformat(),
            "method": "drawn_signature",
            "image_data": data.signature_data,
        },
        "questions_snapshot": [question_payload(q) for q in questions],
    }
    item = HealthAssessment(
        payload_json=json.dumps(payload, ensure_ascii=False),
        risk_status=status,
        red_flags_json=json.dumps(flags, ensure_ascii=False),
        professional_clearance=False,
        completed_at=now,
        updated_at=now,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return assessment_payload(item, db)


def _pdf_answer(value: Any) -> str:
    if value is None or value == "":
        return "Não informado"
    if isinstance(value, bool):
        return "Sim" if value else "Não"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "Não informado"
    return str(value)


def _assessment_pdf_buffer(item: HealthAssessment) -> BytesIO:
    payload = json.loads(item.payload_json or "{}")
    answers = payload.get("answers") or {}
    questions = payload.get("questions_snapshot") or []
    signature = payload.get("signature") if isinstance(payload.get("signature"), dict) else None
    red_flags = json.loads(item.red_flags_json or "[]")

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=34, leftMargin=34, topMargin=34, bottomMargin=34)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("RitTitle", parent=styles["Title"], fontName="Helvetica-Bold",
                           fontSize=20, leading=24, alignment=TA_CENTER, textColor=colors.HexColor("#111827"))
    sub = ParagraphStyle("RitSub", parent=styles["Normal"], fontSize=9, leading=13,
                         alignment=TA_CENTER, textColor=colors.HexColor("#64748B"))
    section = ParagraphStyle("RitSection", parent=styles["Heading2"], fontName="Helvetica-Bold",
                             fontSize=12, leading=15, textColor=colors.HexColor("#111827"), spaceBefore=9, spaceAfter=5)
    qstyle = ParagraphStyle("RitQ", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5,
                            leading=11, textColor=colors.HexColor("#1F2937"))
    astyle = ParagraphStyle("RitA", parent=styles["Normal"], fontSize=8.5, leading=11,
                            textColor=colors.HexColor("#334155"))
    note = ParagraphStyle("RitNote", parent=styles["Normal"], fontSize=8.5, leading=12,
                          textColor=colors.HexColor("#475569"))

    story = [Paragraph("RITMOX", title), Paragraph("Anamnese e triagem pré-participação", sub), Spacer(1, 10)]
    completed = item.completed_at.astimezone().strftime("%d/%m/%Y %H:%M") if item.completed_at else "-"
    status = "Atenção profissional necessária" if item.risk_status == "attention_required" else "Triagem concluída"
    meta = [
        ["Registro", f"#{item.id}"],
        ["Concluída em", completed],
        ["Status", status],
        ["Liberação profissional", item.clearance_provider or ("Sim" if item.professional_clearance else "Não")],
        ["Assinatura", "Assinada" if signature else ("Pendente" if payload.get("signature_requested") else "Não solicitada")],
    ]
    mt = Table(meta, colWidths=[150, 355])
    mt.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#F8FAFC")),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#CBD5E1")),
        ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"), ("FONTSIZE",(0,0),(-1,-1),8.5),
        ("TEXTCOLOR",(0,0),(-1,-1),colors.HexColor("#334155")), ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),7), ("RIGHTPADDING",(0,0),(-1,-1),7),
        ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5),
    ]))
    story += [mt, Spacer(1, 10)]

    current_section = None
    for q in questions:
        sec = str(q.get("section") or "Geral")
        if sec != current_section:
            current_section = sec
            story.append(Paragraph(html_lib.escape(sec), section))
        key = str(q.get("id"))
        question = html_lib.escape(str(q.get("label") or "Pergunta"))
        answer = html_lib.escape(_pdf_answer(answers.get(key)))
        t = Table([[Paragraph(question,qstyle), Paragraph(answer,astyle)]], colWidths=[250,255])
        t.setStyle(TableStyle([
            ("BOX",(0,0),(-1,-1),0.35,colors.HexColor("#D7DEE8")), ("VALIGN",(0,0),(-1,-1),"TOP"),
            ("LEFTPADDING",(0,0),(-1,-1),6), ("RIGHTPADDING",(0,0),(-1,-1),6),
            ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5),
        ]))
        story += [t, Spacer(1, 4)]

    story.append(Paragraph("Declarações", section))
    story.append(Paragraph("✓ Respostas declaradas como verdadeiras e atuais." if payload.get("consent_truthful") else "Declaração de veracidade não confirmada.", note))
    story.append(Paragraph("✓ Ciência de que a triagem não substitui consulta, diagnóstico ou liberação médica quando necessária." if payload.get("consent_screening") else "Declaração de ciência não confirmada.", note))

    if red_flags:
        story.append(Paragraph("Sinais de atenção", section))
        for flag in red_flags:
            story.append(Paragraph("• " + html_lib.escape(str(flag)), note))

    story.append(Paragraph("Assinatura eletrônica", section))
    if signature:
        image_data = str(signature.get("image_data") or "")
        if image_data.startswith("data:image/png;base64,"):
            try:
                image_raw = base64.b64decode(image_data.split(",", 1)[1])
                signature_image = RLImage(BytesIO(image_raw))
                signature_image.drawWidth = 180
                signature_image.drawHeight = 52
                story.append(signature_image)
                story.append(Spacer(1, 4))
            except Exception:
                pass
        story.append(Paragraph(
            "Assinado eletronicamente por <b>" + html_lib.escape(str(signature.get("signer_name") or "-")) +
            "</b> em " + html_lib.escape(str(signature.get("signed_at") or "-")) +
            ". Método: assinatura desenhada no formulário do RITMOX.", note
        ))
    elif payload.get("signature_requested"):
        story.append(Paragraph("Assinatura solicitada e ainda pendente.", note))
    else:
        story.append(Paragraph("Assinatura não registrada.", note))

    story += [Spacer(1,16), Paragraph("Documento gerado automaticamente pelo RITMOX. A triagem não substitui avaliação médica ou profissional quando indicada.", sub)]
    doc.build(story)
    buffer.seek(0)
    return buffer


def _profile_payload(item: UserProfile) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name or "Júnior",
        "email": item.email or "",
        "birth_date": item.birth_date or "",
        "goals": item.goals or "",
        "photo_data": item.photo_data or "",
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _ensure_user_profile(db: Session) -> UserProfile:
    item = db.get(UserProfile, 1)
    if item:
        return item
    item = UserProfile(id=1, name="Júnior")
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.get("/api/profile")
def get_user_profile(db: Session = Depends(session)):
    return _profile_payload(_ensure_user_profile(db))


@app.put("/api/profile")
def update_user_profile(data: UserProfileIn, db: Session = Depends(session)):
    item = _ensure_user_profile(db)
    name = data.name.strip()
    if len(name) < 2:
        raise HTTPException(422, "Informe um nome válido.")
    email = data.email.strip().lower()
    if email and ("@" not in email or "." not in email.split("@")[-1]):
        raise HTTPException(422, "Informe um e-mail válido.")
    birth_date = data.birth_date.strip()
    if birth_date:
        try:
            date.fromisoformat(birth_date)
        except ValueError as exc:
            raise HTTPException(422, "Informe uma data de nascimento válida.") from exc
    photo_data = data.photo_data.strip()
    if photo_data and not photo_data.startswith("data:image/"):
        raise HTTPException(422, "A foto de perfil é inválida.")

    item.name = name
    item.email = email
    item.birth_date = birth_date
    item.goals = data.goals.strip()
    item.photo_data = photo_data
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return _profile_payload(item)


@app.get("/api/profile/anamnesis")
def profile_anamnesis(db: Session = Depends(session)):
    items = db.scalars(select(HealthAssessment).order_by(HealthAssessment.id.desc()).limit(20)).all()
    history = [assessment_payload(item, db) for item in items]
    return {"latest": history[0] if history else None, "history": history, "count": len(history)}


@app.post("/api/health-assessment/{assessment_id}/signature")
def sign_health_assessment(assessment_id: int, data: AssessmentSignatureIn, db: Session = Depends(session)):
    item = db.get(HealthAssessment, assessment_id)
    if not item:
        raise HTTPException(404, "Anamnese não encontrada.")
    payload = json.loads(item.payload_json or "{}")
    if not payload.get("signature_requested"):
        raise HTTPException(409, "Esta anamnese não possui solicitação de assinatura.")
    if not data.accepted:
        raise HTTPException(422, "Confirme a declaração de assinatura eletrônica.")
    if isinstance(payload.get("signature"), dict):
        return assessment_payload(item, db)
    now = datetime.now(timezone.utc)
    payload["signature"] = {"signer_name": data.signer_name.strip(), "signed_at": now.isoformat(), "method": "electronic_attestation"}
    item.payload_json = json.dumps(payload, ensure_ascii=False)
    item.updated_at = now
    db.commit()
    db.refresh(item)
    return assessment_payload(item, db)


@app.get("/api/health-assessment/{assessment_id}/pdf")
def health_assessment_pdf(assessment_id: int, db: Session = Depends(session)):
    item = db.get(HealthAssessment, assessment_id)
    if not item:
        raise HTTPException(404, "Anamnese não encontrada.")
    return StreamingResponse(_assessment_pdf_buffer(item), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="RITMOX_Anamnese_{item.id}.pdf"'})


@app.get("/api/profile/anamnesis/latest/pdf")
def latest_profile_anamnesis_pdf(db: Session = Depends(session)):
    item = db.scalars(select(HealthAssessment).order_by(HealthAssessment.id.desc())).first()
    if not item:
        raise HTTPException(404, "Nenhuma anamnese salva no perfil.")
    return StreamingResponse(_assessment_pdf_buffer(item), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="RITMOX_Anamnese_{item.id}.pdf"'})


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
