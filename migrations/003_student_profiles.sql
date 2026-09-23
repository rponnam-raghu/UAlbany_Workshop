-- Seed once through the migration ledger. Restarts never overwrite edited profiles.
CREATE TABLE student_profiles (
    id UUID PRIMARY KEY,
    details JSONB NOT NULL CHECK (jsonb_typeof(details) = 'object'),
    revision BIGINT NOT NULL DEFAULT 1 CHECK (revision > 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO student_profiles (id, details) VALUES
('10000000-0000-4000-8000-000000000001', '{
  "name": "Avery", "program": "B.S. in Computer Science",
  "intake": {"season": "Spring", "year": 2027},
  "current_term": {"season": "Fall", "year": 2026}, "status": "applicant",
  "completed": [], "in_progress": [],
  "goals": "AI; planning the first semester"
}'),
('10000000-0000-4000-8000-000000000002', '{
  "name": "Sam", "program": "B.S. in Computer Science",
  "intake": {"season": "Fall", "year": 2025},
  "current_term": {"season": "Fall", "year": 2026}, "status": "enrolled",
  "completed": [
    {"code": "CSI 201", "grade": "A"}, {"code": "CSI 213", "grade": "B+"},
    {"code": "MAT 112", "grade": "B"}, {"code": "MAT 214", "grade": "B+"}
  ],
  "in_progress": [{"code": "CSI 333", "grade": null}],
  "goals": "Databases and backend development"
}'),
('10000000-0000-4000-8000-000000000003', '{
  "name": "Maya", "program": "B.S. in Computer Science",
  "intake": {"season": "Fall", "year": 2024},
  "current_term": {"season": "Fall", "year": 2026}, "status": "enrolled",
  "completed": [
    {"code": "CSI 201", "grade": "A"}, {"code": "CSI 213", "grade": "A-"},
    {"code": "CSI 310", "grade": "B+"}, {"code": "CSI 333", "grade": "B"},
    {"code": "MAT 112", "grade": "A"}, {"code": "MAT 214", "grade": "A-"}
  ],
  "in_progress": [{"code": "CSI 445", "grade": null}],
  "goals": "Software engineering and capstone preparation"
}');
