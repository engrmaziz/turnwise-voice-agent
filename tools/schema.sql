CREATE TABLE IF NOT EXISTS patients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    dob TEXT
);

CREATE TABLE IF NOT EXISTS doctors (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS slots (
    id TEXT PRIMARY KEY,
    doctor_id TEXT NOT NULL,
    start_iso TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    taken INTEGER NOT NULL DEFAULT 0,
    UNIQUE (doctor_id, start_iso),
    FOREIGN KEY (doctor_id) REFERENCES doctors(id)
);

CREATE TABLE IF NOT EXISTS appointments (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    doctor_id TEXT NOT NULL,
    start_iso TEXT NOT NULL,
    status TEXT NOT NULL,
    slots_json TEXT NOT NULL,
    FOREIGN KEY (patient_id) REFERENCES patients(id),
    FOREIGN KEY (doctor_id) REFERENCES doctors(id)
);

CREATE TABLE IF NOT EXISTS idempotency (
    key TEXT PRIMARY KEY,
    appointment_id TEXT NOT NULL,
    FOREIGN KEY (appointment_id) REFERENCES appointments(id)
);
