import os
import re

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite://")

from app import Claim, CustomerPolicy, CustomerQuestion, Payment, Policy, User, app, db, ensure_default_admin


@pytest.fixture(autouse=True)
def reset_database():
    with app.app_context():
        db.drop_all()
        db.create_all()
        if not Policy.query.first():
            from app import seed_policies
            seed_policies()
        ensure_default_admin()


def test_homepage_renders():
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"InsureCare" in resp.data or b"Protection for the things" in resp.data


def test_policies_page_renders():
    client = app.test_client()
    resp = client.get("/policies")
    assert resp.status_code == 200
    assert b"Insurance policies" in resp.data


def test_registration_creates_user():
    client = app.test_client()
    payload = {
        "full_name": "Jane User",
        "username": "jane_user_real",
        "email": "jane@example.com",
        "phone": "5551234567",
        "password": "securepass123",
        "confirm_password": "securepass123",
    }
    resp = client.post("/register", data=payload, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Your account has been created successfully." in resp.data


def test_customer_can_submit_question():
    client = app.test_client()
    client.post("/register", data={
        "full_name": "Customer One",
        "username": "customer_one",
        "email": "customer1@example.com",
        "phone": "5550001111",
        "password": "securepass123",
        "confirm_password": "securepass123",
    }, follow_redirects=True)

    resp = client.post("/ask_question", data={"question": "How do I renew my policy?"}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"How do I renew my policy?" in resp.data
    assert b"CUSTOMER PORTAL" in resp.data
    assert b"Available Policies" in resp.data
    assert b"Apply Policy" in resp.data
    assert b"Apply" in resp.data


def test_admin_can_approve_policy_application():
    client = app.test_client()
    with app.app_context():
        from app import User, Policy, CustomerPolicy, db
        user = User(
            full_name="Demo User",
            username="demo_policy_user",
            email="demo_policy@example.com",
            phone="5551239876",
            customer_id="CUST-9001",
            role="customer",
        )
        user.set_password("securepass123")
        db.session.add(user)
        db.session.commit()
        policy = Policy.query.first()
        enrollment = CustomerPolicy(user_id=user.id, policy_id=policy.id, status="pending")
        db.session.add(enrollment)
        db.session.commit()

        admin = User.query.filter_by(username="bipasa").first()
        client.post("/login", data={"username": admin.username, "password": "bipasa@1234"}, follow_redirects=True)
        resp = client.post(f"/admin/approve_policy/{enrollment.id}", follow_redirects=True)
        assert resp.status_code == 200
        assert b"approved" in resp.data.lower()


def test_admin_dashboard_displays_operational_metrics():
    client = app.test_client()
    with app.app_context():
        customer = User(
            full_name="Metrics Customer",
            username="metrics_customer",
            email="metrics@example.com",
            phone="5551230000",
            customer_id="CUST-METRICS",
            role="customer",
        )
        customer.set_password("securepass123")
        db.session.add(customer)
        db.session.commit()

        policy = Policy.query.first()
        active_enrollment = CustomerPolicy(user_id=customer.id, policy_id=policy.id, status="active")
        pending_enrollment = CustomerPolicy(user_id=customer.id, policy_id=policy.id, status="pending")
        db.session.add_all([active_enrollment, pending_enrollment])
        db.session.commit()
        db.session.add(Payment(
            customer_policy_id=active_enrollment.id,
            reference="PAY-METRICS-1",
            amount=1250,
            status="paid",
        ))
        db.session.add(CustomerQuestion(user_id=customer.id, question="Metrics question", status="open"))
        db.session.add(Claim(
            customer_policy_id=active_enrollment.id,
            claim_reference="CLM-METRICS-1",
            claim_amount=500,
            description="Metrics claim",
            status="under_review",
        ))
        db.session.commit()

    client.post("/login", data={"username": "bipasa", "password": "bipasa@1234"}, follow_redirects=True)
    response = client.get("/admin")

    assert response.status_code == 200
    assert re.search(rb"Total policy holders\s*</small>\s*<strong>2</strong>", response.data)
    assert re.search(rb"Approved policy holders\s*</small>\s*<strong>1</strong>", response.data)
    assert re.search(rb"Disapproved policy holders\s*</small>\s*<strong>0</strong>", response.data)
    assert re.search(rb"Waiting for approval\s*</small>\s*<strong>1</strong>", response.data)
    assert b"Rs. 1250.00" in response.data
    assert b"Search customers" in response.data


def test_admin_can_update_policy_details():
    client = app.test_client()
    client.post("/login", data={"username": "bipasa", "password": "bipasa@1234"}, follow_redirects=True)

    with app.app_context():
        policy = Policy.query.first()
        policy_id = policy.id

    response = client.post(f"/admin/update_policy/{policy_id}", data={
        "name": "Updated SafeDrive",
        "category": "Auto",
        "description": "Updated policy description.",
        "policy_code": "SD-UPDATED",
        "premium_amount": "1450.50",
        "duration_months": "18",
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Policy updated successfully." in response.data
    with app.app_context():
        policy = db.session.get(Policy, policy_id)
        assert policy.name == "Updated SafeDrive"
        assert policy.policy_code == "SD-UPDATED"
        assert policy.premium_amount == 1450.50
        assert policy.duration_months == 18
