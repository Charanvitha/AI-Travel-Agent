from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import os, re
from copy import deepcopy
from dotenv import load_dotenv
from flask import Flask, jsonify, request, session, send_from_directory
from flask_cors import CORS
from sqlalchemy import text
from .models import db, User, FamilyProfile, Trip, TripVersion
from .providers import PlacesProvider, WeatherProvider, LLMProvider

load_dotenv()

def create_app(test_config=None):
    app = Flask(__name__)
    database_url = os.getenv("DATABASE_URL", "sqlite:///atlasai.db")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    app.config.update(SECRET_KEY=os.getenv("SECRET_KEY", "dev-only-change-me"), SQLALCHEMY_DATABASE_URI=database_url, SQLALCHEMY_TRACK_MODIFICATIONS=False, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=os.getenv("FLASK_ENV") == "production")
    if test_config: app.config.update(test_config)
    db.init_app(app)
    CORS(app, supports_credentials=True, origins=[os.getenv("FRONTEND_URL", "http://localhost:5173")])
    app.places, app.weather, app.llm = PlacesProvider(), WeatherProvider(), LLMProvider()
    with app.app_context(): db.create_all()

    def current_user():
        user_id = session.get("user_id")
        return db.session.get(User, user_id) if user_id else None
    def auth_required(fn):
        from functools import wraps
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not current_user(): return jsonify(error="Please sign in to continue."), 401
            return fn(*args, **kwargs)
        return wrapped
    def owned_trip(trip_id):
        user = current_user()
        return Trip.query.filter_by(id=trip_id, user_id=user.id).first() if user else None
    def trip_json(t):
        return {"id": t.id, "origin": t.origin, "destination": t.destination, "startDate": t.start_date, "endDate": t.end_date, "budget": str(t.total_budget), "currency": t.currency, "travelMode": t.travel_mode, "status": t.status, "currentVersion": t.current_version, "itinerary": t.itinerary or {}, "checklist": t.checklist or [], "messages": t.messages or []}
    def error(message, code=400): return jsonify(error=message), code

    @app.get("/api/health")
    def health(): return jsonify(status="ok", brand="AtlasAI", mode="demo")

    @app.post("/api/auth/register")
    def register():
        data = request.get_json(silent=True) or {}
        name, email, password = str(data.get("name", "")).strip(), str(data.get("email", "")).strip().lower(), str(data.get("password", ""))
        if not name or len(name) > 120 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email): return error("Enter your name and a valid email address.")
        if len(password) < 8: return error("Use a password with at least 8 characters.")
        if User.query.filter_by(email=email).first(): return error("An account with this email already exists.", 409)
        user = User(name=name, email=email); user.set_password(password); db.session.add(user); db.session.flush()
        db.session.add(FamilyProfile(user_id=user.id)); db.session.commit(); session["user_id"] = user.id
        return jsonify(user_json(user)), 201

    def user_json(user): return {"id": user.id, "name": user.name, "email": user.email, "preferredLanguage": user.preferred_language}

    @app.post("/api/auth/login")
    def login():
        data = request.get_json(silent=True) or {}; user = User.query.filter_by(email=str(data.get("email", "")).strip().lower()).first()
        if not user or not user.check_password(str(data.get("password", ""))): return error("Email or password is incorrect.", 401)
        session.clear(); session["user_id"] = user.id
        return jsonify(user_json(user))

    @app.post("/api/auth/logout")
    def logout(): session.clear(); return jsonify(ok=True)

    @app.get("/api/auth/me")
    def me():
        user = current_user()
        return (jsonify(user_json(user)) if user else (jsonify(error="Not signed in."), 401))

    @app.route("/api/family-profile", methods=["GET", "PUT"])
    @auth_required
    def family_profile():
        user = current_user(); profile = user.family_profile
        if request.method == "PUT":
            data = request.get_json(silent=True) or {}
            adults = data.get("adultsCount", profile.adults_count)
            if not isinstance(adults, int) or not 1 <= adults <= 12: return error("Adults must be between 1 and 12.")
            profile.adults_count = adults
            for key, col in [("childrenAgeRanges", "children_age_ranges"), ("dietaryPreferences", "dietary_preferences"), ("accessibilityNeeds", "accessibility_needs"), ("interests", "interests")]:
                value = data.get(key, getattr(profile, col)); setattr(profile, col, value if isinstance(value, list) else [])
            profile.travel_pace = data.get("travelPace", profile.travel_pace); db.session.commit()
        return jsonify({"adultsCount": profile.adults_count, "childrenAgeRanges": profile.children_age_ranges or [], "dietaryPreferences": profile.dietary_preferences or [], "accessibilityNeeds": profile.accessibility_needs or [], "travelPace": profile.travel_pace, "interests": profile.interests or []})

    @app.route("/api/trips", methods=["GET", "POST"])
    @auth_required
    def trips():
        user = current_user()
        if request.method == "GET": return jsonify([trip_json(x) for x in Trip.query.filter_by(user_id=user.id).order_by(Trip.created_at.desc()).all()])
        d = request.get_json(silent=True) or {}
        try:
            start, end = date.fromisoformat(d.get("startDate", "")), date.fromisoformat(d.get("endDate", ""))
            budget = Decimal(str(d.get("budget", "")))
        except (ValueError, InvalidOperation, TypeError): return error("Enter valid travel dates and a numeric budget.")
        if start < date.today() or end < start: return error("Choose a future departure date and a return date on or after departure.")
        if (end - start).days > 30: return error("Trips can be up to 30 nights in demo mode.")
        if budget <= 0 or budget > Decimal("99999999"): return error("Budget must be a positive amount.")
        origin, destination = str(d.get("origin", "")).strip(), str(d.get("destination", "")).strip()
        if not origin or not destination: return error("Origin and destination are required.")
        currency = str(d.get("currency", "INR")).upper()
        if not re.fullmatch(r"[A-Z]{3}", currency): return error("Currency must be a three-letter currency code.")
        trip = Trip(user_id=user.id, origin=origin[:160], destination=destination[:160], start_date=start.isoformat(), end_date=end.isoformat(), total_budget=budget, currency=currency, travel_mode=str(d.get("travelMode", "Car"))[:40])
        trip.checklist = default_checklist(); db.session.add(trip); db.session.commit()
        return jsonify(trip_json(trip)), 201

    def default_checklist(): return [{"id": str(i), "label": label, "done": False} for i, label in enumerate(["Check travel documents", "Pack weather-ready clothing", "Bring children’s essentials", "Add parent-entered medication reminders", "Pack snacks and refillable water", "Save important contacts"])]

    @app.route("/api/trips/<trip_id>", methods=["GET", "PATCH", "DELETE"])
    @auth_required
    def trip_detail(trip_id):
        trip = owned_trip(trip_id)
        if not trip: return error("Trip not found.", 404)
        if request.method == "GET": return jsonify(trip_json(trip))
        if request.method == "DELETE": db.session.delete(trip); db.session.commit(); return jsonify(ok=True)
        d = request.get_json(silent=True) or {}
        if "budget" in d:
            try: amount = Decimal(str(d["budget"]))
            except InvalidOperation: return error("Budget must be numeric.")
            if amount <= 0: return error("Budget must be positive.")
            trip.total_budget = amount
        if "status" in d and d["status"] in ("planning", "upcoming", "completed"): trip.status = d["status"]
        db.session.commit(); return jsonify(trip_json(trip))

    def generate_plan(trip, reason="Initial plan"):
        days = (date.fromisoformat(trip.end_date) - date.fromisoformat(trip.start_date)).days + 1
        candidates = app.places.search("", trip.destination)
        profile = trip.user.family_profile
        preference_categories = {
            "nature": {"nature", "garden", "outdoor", "coast", "waterway"},
            "museums": {"museum", "gallery"}, "history": {"heritage", "culture"},
            "animals": {"nature"}, "arts & crafts": {"gallery", "culture"},
            "easy walks": {"garden", "outdoor", "coast"}, "food": {"food"},
        }
        interests = [str(x).casefold() for x in (profile.interests or [])]
        preferred_categories = set().union(*(preference_categories.get(x, set()) for x in interests)) if interests else set()
        if preferred_categories:
            candidates = sorted(candidates, key=lambda place: place["category"].casefold() not in preferred_categories)
        pace = (profile.travel_pace or "balanced").casefold()
        places_per_day = {"relaxed": 1, "balanced": 2, "adventurous": 3}.get(pace, 2)
        if not candidates:
            itinerary = {"days": [], "estimatedTotal": "0", "budget": str(trip.total_budget), "currency": trip.currency,
                         "isEstimate": True, "source": "No curated sample data for this destination",
                         "withinBudget": False, "personalization": {"travelPace": pace, "placesPerDay": places_per_day,
                         "interestsUsed": interests, "adultsCount": profile.adults_count, "childrenAgeRanges": profile.children_age_ranges or []},
                         "warnings": ["No named demo places are available for this destination yet. No itinerary or daily cost estimate was generated."]}
            trip.current_version += 1; trip.itinerary = itinerary
            db.session.add(TripVersion(trip_id=trip.id, version_number=trip.current_version, reason=reason, itinerary_snapshot=itinerary)); db.session.commit()
            return itinerary
        items = []
        for day in range(days):
            picked = candidates[day * places_per_day:day * places_per_day + places_per_day]
            local_date = (date.fromisoformat(trip.start_date) + timedelta(days=day)).isoformat()
            day_items, hour = [], 9
            for place in picked:
                cost = place["cost"]
                visit_hours = max(1, (place["duration"] + 59) // 60)
                day_items.append({"id": f"d{day+1}i{len(day_items)+1}", "title": place["name"], "area": place["area"], "category": place["category"], "description": place["description"], "startTime": f"{hour:02}:00", "endTime": f"{hour + visit_hours:02}:00", "durationMinutes": place["duration"], "estimatedCost": str(cost) if cost is not None else None, "currency": trip.currency, "travelMinutes": None, "source": place["source"], "suitability": place["suitability"]})
                hour += visit_hours + 1
            items.append({"dayNumber": day+1, "date": local_date, "items": day_items, "estimatedDailyCost": str(sum((Decimal(x["estimatedCost"]) for x in day_items if x["estimatedCost"] is not None), Decimal("0")) + Decimal("500"))})
        activity_sum = sum((Decimal(item["estimatedCost"]) for day in items for item in day["items"] if item["estimatedCost"] is not None), Decimal("0"))
        total = activity_sum + Decimal("500") * days
        warnings = []
        if any(item["estimatedCost"] is None for day in items for item in day["items"]): warnings.append("Venue entry fees, meals, local transport and accommodation are not included. Check current prices with each provider.")
        if total > trip.total_budget: warnings.append("This partial estimate exceeds the entered budget. Use Budget rescue to see a lower-cost draft.")
        itinerary = {"days": items, "estimatedTotal": str(total), "budget": str(trip.total_budget), "currency": trip.currency, "isEstimate": True, "source": "Named demo places · entry fees are not verified", "withinBudget": total <= trip.total_budget, "personalization": {"travelPace": pace, "placesPerDay": places_per_day, "interestsUsed": interests, "adultsCount": profile.adults_count, "childrenAgeRanges": profile.children_age_ranges or []}, "warnings": warnings}
        if profile.accessibility_needs or profile.dietary_preferences:
            warnings.append("Your dietary and access preferences are saved, but demo place data does not verify venue details. Confirm directly before visiting.")
        trip.current_version += 1; trip.itinerary = itinerary
        db.session.add(TripVersion(trip_id=trip.id, version_number=trip.current_version, reason=reason, itinerary_snapshot=itinerary)); db.session.commit()
        return itinerary

    def planning_endpoint(trip_id, action):
        trip = owned_trip(trip_id)
        if not trip: return error("Trip not found.", 404)
        if action == "plan": plan = generate_plan(trip)
        elif action == "replan": plan = generate_plan(trip, (request.get_json(silent=True) or {}).get("reason", "Family requested a replan"))
        elif action == "optimize-budget":
            try:
                data = request.get_json(silent=True) or {}
                if "budget" in data: trip.total_budget = Decimal(str(data["budget"]))
                if trip.itinerary:
                    updated = deepcopy(trip.itinerary)
                    for day in updated.get("days", []):
                        day["items"] = [i for i in day["items"] if i["category"] not in ("Activity", "Culture")]
                    days = updated.get("days", [])
                    total = sum((Decimal(i["estimatedCost"]) for day in days for i in day["items"] if i["estimatedCost"] is not None), Decimal("0")) + Decimal("500") * len(days)
                    updated.update(estimatedTotal=str(total), budget=str(trip.total_budget), withinBudget=total <= trip.total_budget, warnings=["Reduced-cost demo draft. Venue entry fees and transport are not included; check live prices."])
                    trip.itinerary = updated
                else: plan = generate_plan(trip, "Budget rescue")
                trip.current_version += 1
                plan = trip.itinerary
                db.session.add(TripVersion(trip_id=trip.id, version_number=trip.current_version, reason="Budget rescue", itinerary_snapshot=plan)); db.session.commit()
            except (InvalidOperation, ValueError): return error("Budget must be a valid amount.")
        elif action == "validate":
            plan = trip.itinerary or {}; issues = []
            if not plan: issues.append("No itinerary has been generated yet.")
            if plan and Decimal(plan.get("estimatedTotal", "0")) > trip.total_budget: issues.append("Estimated costs exceed the trip budget.")
            return jsonify(valid=not issues, issues=issues, source="demo estimates")
        return jsonify(plan)

    for suffix, action in [("plan", "plan"), ("replan", "replan"), ("optimize-budget", "optimize-budget"), ("validate", "validate")]:
        def make_view(action_name):
            @app.post(f"/api/trips/<trip_id>/{action_name}", endpoint=f"trip_{action_name.replace('-', '_')}")
            @auth_required
            def view(trip_id): return planning_endpoint(trip_id, action_name)
            view.__name__ = f"trip_{action_name.replace('-', '_')}"
            return view
        make_view(action)

    @app.get("/api/trips/<trip_id>/versions")
    @auth_required
    def versions(trip_id):
        trip = owned_trip(trip_id)
        if not trip: return error("Trip not found.", 404)
        return jsonify([{"versionNumber": v.version_number, "reason": v.reason, "createdAt": v.created_at.isoformat(), "itinerary": v.itinerary_snapshot} for v in TripVersion.query.filter_by(trip_id=trip.id).order_by(TripVersion.version_number.desc()).all()])

    @app.post("/api/trips/<trip_id>/restore-version")
    @auth_required
    def restore_version(trip_id):
        trip = owned_trip(trip_id)
        if not trip: return error("Trip not found.", 404)
        number = (request.get_json(silent=True) or {}).get("versionNumber")
        version = TripVersion.query.filter_by(trip_id=trip.id, version_number=number).first()
        if not version: return error("Version not found.", 404)
        trip.current_version += 1; trip.itinerary = version.itinerary_snapshot
        db.session.add(TripVersion(trip_id=trip.id, version_number=trip.current_version, reason=f"Restored version {number}", itinerary_snapshot=trip.itinerary)); db.session.commit()
        return jsonify(trip_json(trip))

    @app.get("/api/places/search")
    def places_search(): return jsonify({"source": "demo data", "results": app.places.search(request.args.get("q", ""), request.args.get("destination", "Hyderabad"))})

    @app.get("/api/weather")
    def weather(): return jsonify(app.weather.forecast(request.args.get("destination", ""), request.args.get("date")))

    @app.route("/api/trips/<trip_id>/checklist", methods=["GET", "PATCH"])
    @auth_required
    def checklist(trip_id):
        trip = owned_trip(trip_id)
        if not trip: return error("Trip not found.", 404)
        if request.method == "PATCH":
            data = request.get_json(silent=True) or {}; changes = data.get("items", [])
            if isinstance(changes, list):
                by_id = {item.get("id"): dict(item) for item in trip.checklist or []}
                for change in changes:
                    if change.get("id") in by_id: by_id[change["id"]]["done"] = bool(change.get("done"))
                trip.checklist = list(by_id.values()); db.session.commit()
        return jsonify(trip.checklist or [])

    @app.route("/api/trips/<trip_id>/messages", methods=["GET", "POST"])
    @app.post("/api/trips/<trip_id>/chat")
    @auth_required
    def chat(trip_id):
        trip = owned_trip(trip_id)
        if not trip: return error("Trip not found.", 404)
        if request.method == "GET": return jsonify(trip.messages or [])
        prompt = str((request.get_json(silent=True) or {}).get("message", "")).strip()
        if not prompt or len(prompt) > 2000: return error("Enter a message of up to 2,000 characters.")
        answer = app.llm.respond(prompt, {"destination": trip.destination, "itinerary": trip.itinerary})
        messages = list(trip.messages or []) + [{"role": "user", "content": prompt}, {"role": "assistant", "content": answer, "source": "demo assistant"}]
        trip.messages = messages[-100:]; db.session.commit(); return jsonify(messages[-2:])

    @app.errorhandler(500)
    def server_error(exc): db.session.rollback(); return jsonify(error="Something went wrong. Please try again."), 500
    @app.get("/")
    @app.get("/<path:asset>")
    def frontend_asset(asset="index.html"):
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
        candidate = os.path.join(root, asset)
        if os.path.isfile(candidate): return send_from_directory(root, asset)
        if "." not in asset: return send_from_directory(root, "index.html")
        return jsonify(error="Not found."), 404
    return app

if __name__ == "__main__": create_app().run(debug=os.getenv("FLASK_ENV") == "development", port=5000)
