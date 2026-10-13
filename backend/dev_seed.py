"""Development-only seed data. ALL PEOPLE BELOW ARE FICTIONAL.

    set DEV_SEED_PASSWORD=<choose a password: 12+ chars, mixed case, a digit>
    python dev_seed.py

Creates one user per role (usernames: dev.admin, dev.nurse, dev.clinician, dev.coordinator,
dev.pharmacist, dev.patient), two fictional patients, one clinician and a few future appointment
slots.  Refuses to run when APP_ENV=production.  The password comes from the environment so no
credential is stored in this repository.
"""
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from auth import create_user
from config import get_settings
from database import SessionLocal, init_db
from models_care import Appointment, AppointmentSlot, Clinician, Patient, User
from patient_matching import normalize_name, phonetic_key


def main() -> int:
    settings = get_settings()
    if settings.is_production:
        print("Refusing to seed data when APP_ENV=production.", file=sys.stderr)
        return 1
    password = os.getenv("DEV_SEED_PASSWORD")
    if not password:
        print("Set DEV_SEED_PASSWORD (12+ chars, mixed case, with a digit) and run again.", file=sys.stderr)
        return 1

    init_db()
    with SessionLocal() as db:
        if db.query(User).filter(User.username == "dev.admin").first():
            print("Seed data already present; nothing to do.")
            return 0

        def person(name, dob, phone, mrn):
            p = Patient(full_name=name, name_key=normalize_name(name), phonetic_key=phonetic_key(name),
                        date_of_birth=dob, phone=phone, mrn=mrn, contact_preference="in_app",
                        preferred_language="en", identity_verified=True)
            db.add(p)
            db.flush()
            return p

        portal_patient = person("Asha Fictional-Rao", datetime(1986, 4, 9).date(), "+91 90000 00001", "DEV-0001")
        person("Akshay Fictional-Kumar", datetime(1984, 5, 12).date(), "+91 90000 00002", "DEV-0002")

        create_user(db, username="dev.admin", password=password, full_name="Dev Administrator", role="admin")
        create_user(db, username="dev.nurse", password=password, full_name="Dev Nurse", role="nurse")
        create_user(db, username="dev.clinician", password=password, full_name="Dr. Dev Clinician", role="clinician")
        create_user(db, username="dev.coordinator", password=password, full_name="Dev Coordinator", role="coordinator",
                    department="Outpatient & Appointment Coordination")
        create_user(db, username="dev.pharmacist", password=password, full_name="Dev Pharmacist", role="pharmacist",
                    department="Pharmacy & Therapeutics")
        create_user(db, username="dev.patient", password=password, full_name="Asha Fictional-Rao", role="patient",
                    patient_id=portal_patient.id)

        doc = Clinician(full_name="Dr. Fictional Iyer", department="Cardiology", specialty="Cardiologist", location="Main Campus")
        db.add(doc)
        db.flush()
        tz = ZoneInfo(settings.hospital_timezone)
        start = (datetime.now(tz) + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)
        for i in range(6):
            s = (start + timedelta(minutes=20 * i)).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
            db.add(AppointmentSlot(clinician_id=doc.id, start_utc=s, end_utc=s + timedelta(minutes=20)))
        db.commit()
        print("Seeded 6 users (dev.admin, dev.nurse, dev.clinician, dev.coordinator, dev.pharmacist, dev.patient), "
              "2 fictional patients, 1 clinician and 6 slots.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
