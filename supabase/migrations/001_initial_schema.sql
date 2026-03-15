-- FeedbackOS — Initial Schema
-- Run this in the Supabase SQL Editor to set up all tables.
-- Designed to match api/models/schemas.py exactly.

-- ============================================================
-- EXTENSIONS
-- ============================================================

create extension if not exists "uuid-ossp";


-- ============================================================
-- ENUMS
-- ============================================================

create type user_role as enum ('student', 'ta', 'instructor');
create type submission_status as enum ('submitted', 'under_review', 'reviewed', 'resubmitted');
create type review_status as enum ('draft', 'submitted', 'delivered');
create type score_value as enum ('green', 'yellow', 'red', 'not_applicable', 'flagged_for_help');
create type action_item_source as enum ('ta_written', 'ai_suggested_accepted', 'ai_suggested_edited');
create type dimension_category as enum (
  'code_quality', 'error_handling', 'architecture', 'llm_usage',
  'deployment', 'documentation', 'prompt_eng', 'stack_specific'
);
create type rubric_type as enum ('universal', 'overlay');
create type author_role as enum ('student', 'ta');


-- ============================================================
-- CORE TABLES
-- ============================================================

-- Users (extends Supabase auth.users)
create table users (
  id           uuid primary key default uuid_generate_v4(),
  email        text not null unique,
  name         text not null,
  role         user_role not null default 'student',
  cohort_id    uuid,  -- FK added after cohorts table
  github_username text,
  discord_id   text,
  created_at   timestamptz not null default now()
);

-- Cohorts
create table cohorts (
  id          uuid primary key default uuid_generate_v4(),
  name        text not null,
  start_date  date,
  end_date    date,
  created_at  timestamptz not null default now()
);

alter table users
  add constraint users_cohort_id_fkey
  foreign key (cohort_id) references cohorts(id) on delete set null;

-- Rubrics
create table rubrics (
  id           uuid primary key default uuid_generate_v4(),
  name         text not null,
  type         rubric_type not null default 'universal',
  stack_tag    text,           -- e.g. 'streamlit', 'gradio' — null for universal
  created_at   timestamptz not null default now()
);

-- Rubric dimensions
create table rubric_dimensions (
  id          uuid primary key default uuid_generate_v4(),
  rubric_id   uuid not null references rubrics(id) on delete cascade,
  name        text not null,
  description text not null,
  category    dimension_category not null,
  sort_order  int not null default 0,
  is_required boolean not null default true,
  stack_tags  text[] default '{}',
  created_at  timestamptz not null default now()
);

create index rubric_dimensions_rubric_id_idx on rubric_dimensions(rubric_id);

-- Assignments
create table assignments (
  id          uuid primary key default uuid_generate_v4(),
  cohort_id   uuid not null references cohorts(id) on delete cascade,
  title       text not null,
  description text,
  rubric_id   uuid references rubrics(id) on delete set null,
  due_date    timestamptz,
  created_at  timestamptz not null default now()
);

create index assignments_cohort_id_idx on assignments(cohort_id);

-- Submissions
create table submissions (
  id              uuid primary key default uuid_generate_v4(),
  assignment_id   uuid not null references assignments(id) on delete cascade,
  student_id      uuid not null references users(id) on delete cascade,
  ta_id           uuid references users(id) on delete set null,
  github_repo_url text not null,
  commit_sha      text,
  status          submission_status not null default 'submitted',
  is_flagged      boolean not null default false,
  flag_note       text,
  submitted_at    timestamptz not null default now(),
  created_at      timestamptz not null default now(),
  constraint submissions_repo_commit_unique unique (github_repo_url, commit_sha)
);

create index submissions_student_id_idx on submissions(student_id);
create index submissions_ta_id_idx      on submissions(ta_id);
create index submissions_status_idx     on submissions(status);
create index submissions_assignment_idx on submissions(assignment_id);

-- Submission files (indexed content for code viewer)
create table submission_files (
  id              uuid primary key default uuid_generate_v4(),
  submission_id   uuid not null references submissions(id) on delete cascade,
  filepath        text not null,
  content_preview text,   -- first ~100 lines of file content
  created_at      timestamptz not null default now(),
  constraint submission_files_unique unique (submission_id, filepath)
);

create index submission_files_submission_id_idx on submission_files(submission_id);

-- Detected stacks (separate table, populated async after submission)
create table detected_stacks (
  id                  uuid primary key default uuid_generate_v4(),
  submission_id       uuid not null references submissions(id) on delete cascade unique,
  frontend            text,
  backend             text,
  llm_api             text,
  deployment_platform text,
  confidence          float not null default 0.0,
  raw_tags            text[] default '{}',
  detected_at         timestamptz not null default now()
);

-- Reviews
create table reviews (
  id              uuid primary key default uuid_generate_v4(),
  submission_id   uuid not null references submissions(id) on delete cascade,
  ta_id           uuid not null references users(id) on delete restrict,
  status          review_status not null default 'draft',
  overall_comment text,
  submitted_at    timestamptz,
  delivered_at    timestamptz,
  created_at      timestamptz not null default now(),
  constraint reviews_submission_ta_unique unique (submission_id, ta_id)
);

create index reviews_submission_id_idx on reviews(submission_id);
create index reviews_ta_id_idx         on reviews(ta_id);
create index reviews_status_idx        on reviews(status);

-- Review scores (one row per dimension per review)
create table review_scores (
  id                  uuid primary key default uuid_generate_v4(),
  review_id           uuid not null references reviews(id) on delete cascade,
  dimension_id        uuid not null references rubric_dimensions(id) on delete cascade,
  score               score_value not null,
  comment             text,
  action_item         text,
  action_item_source  action_item_source,
  is_flagged_for_help boolean not null default false,
  flag_note           text,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  constraint review_scores_review_dimension_unique unique (review_id, dimension_id)
);

create index review_scores_review_id_idx     on review_scores(review_id);
create index review_scores_dimension_id_idx  on review_scores(dimension_id);

-- Example feedback (curated + auto-collected)
create table example_feedback (
  id               uuid primary key default uuid_generate_v4(),
  dimension_id     uuid not null references rubric_dimensions(id) on delete cascade,
  stack_tag        text,          -- null means "all stacks"
  score            score_value not null,
  comment          text not null,
  action_item      text,
  was_acted_on     boolean not null default false,
  source_review_id uuid references reviews(id) on delete set null,
  created_at       timestamptz not null default now()
);

create index example_feedback_dimension_id_idx on example_feedback(dimension_id);

-- Dialogue logs (Discord thread messages)
create table dialogue_logs (
  id                  uuid primary key default uuid_generate_v4(),
  review_id           uuid not null references reviews(id) on delete cascade,
  discord_message_id  text,
  author_discord_id   text not null,
  author_role         author_role not null,
  content             text not null,
  thread_id           text,
  created_at          timestamptz not null default now()
);

create index dialogue_logs_review_id_idx on dialogue_logs(review_id);

-- Comprehension events (commit tracking)
create table comprehension_events (
  id                  uuid primary key default uuid_generate_v4(),
  review_id           uuid not null references reviews(id) on delete cascade,
  review_score_id     uuid references review_scores(id) on delete set null,
  student_id          uuid references users(id) on delete set null,
  commit_sha          text not null,
  commit_timestamp    timestamptz not null,
  files_changed       text[] not null default '{}',
  addressed           boolean not null,
  hours_after_delivery float,
  created_at          timestamptz not null default now()
);

create index comprehension_events_review_id_idx on comprehension_events(review_id);
create index comprehension_events_student_id_idx on comprehension_events(student_id);


-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

alter table users                 enable row level security;
alter table cohorts               enable row level security;
alter table assignments           enable row level security;
alter table rubrics               enable row level security;
alter table rubric_dimensions     enable row level security;
alter table submissions           enable row level security;
alter table submission_files      enable row level security;
alter table detected_stacks       enable row level security;
alter table reviews               enable row level security;
alter table review_scores         enable row level security;
alter table example_feedback      enable row level security;
alter table dialogue_logs         enable row level security;
alter table comprehension_events  enable row level security;


-- ============================================================
-- RLS POLICIES
-- ============================================================
-- NOTE: The FastAPI backend uses the SERVICE ROLE key and bypasses RLS.
-- These policies govern direct Supabase client access (e.g. Streamlit
-- frontend using the anon key with a Supabase JWT).
-- For the initial build, allow all authenticated users to read everything
-- and the service role to write everything.  Tighten per-role later.

-- Allow all authenticated users to read all tables
create policy "authenticated read all"
  on users for select to authenticated using (true);
create policy "authenticated read cohorts"
  on cohorts for select to authenticated using (true);
create policy "authenticated read assignments"
  on assignments for select to authenticated using (true);
create policy "authenticated read rubrics"
  on rubrics for select to authenticated using (true);
create policy "authenticated read dimensions"
  on rubric_dimensions for select to authenticated using (true);
create policy "authenticated read submissions"
  on submissions for select to authenticated using (true);
create policy "authenticated read sub files"
  on submission_files for select to authenticated using (true);
create policy "authenticated read stacks"
  on detected_stacks for select to authenticated using (true);
create policy "authenticated read reviews"
  on reviews for select to authenticated using (true);
create policy "authenticated read scores"
  on review_scores for select to authenticated using (true);
create policy "authenticated read examples"
  on example_feedback for select to authenticated using (true);
create policy "authenticated read dialogue"
  on dialogue_logs for select to authenticated using (true);
create policy "authenticated read comprehension"
  on comprehension_events for select to authenticated using (true);

-- Students can only read their own submissions and reviews
-- (Override the broad "authenticated read submissions" policy above when needed)

-- Allow TAs to insert/update reviews and scores via service key (bypasses RLS)
-- All writes from FastAPI use the SERVICE ROLE key → RLS not applied


-- ============================================================
-- UPDATED_AT TRIGGER
-- ============================================================

create or replace function update_updated_at_column()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger review_scores_updated_at
  before update on review_scores
  for each row execute function update_updated_at_column();


-- ============================================================
-- USEFUL VIEWS
-- ============================================================

-- Active review queue: pending submissions with student + stack info
create or replace view review_queue as
select
  s.id              as submission_id,
  s.status,
  s.is_flagged,
  s.flag_note,
  s.submitted_at,
  s.github_repo_url,
  s.commit_sha,
  u.id              as student_id,
  u.name            as student_name,
  u.github_username,
  u.discord_id,
  a.id              as assignment_id,
  a.title           as assignment_title,
  ds.frontend,
  ds.backend,
  ds.llm_api,
  ds.deployment_platform,
  ds.confidence     as stack_confidence
from submissions s
join users u        on u.id = s.student_id
join assignments a  on a.id = s.assignment_id
left join detected_stacks ds on ds.submission_id = s.id
where s.status in ('submitted', 'under_review')
order by s.is_flagged desc, s.submitted_at asc;
