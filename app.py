from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///mileage.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# -------------------------
# DATABASE MODEL
# -------------------------
class MileageLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fuel_type = db.Column(db.String(20), nullable=False)
    distance = db.Column(db.Float, default=0)  # Petrol warmup has distance=0
    fuel_used = db.Column(db.Float, nullable=False)
    fuel_price = db.Column(db.Float, nullable=False)  # required for cost calc
    mileage = db.Column(db.Float, default=0)
    cost_per_km = db.Column(db.Float, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "fuel_type": self.fuel_type,
            "distance": self.distance,
            "fuel_used": self.fuel_used,
            "fuel_price": self.fuel_price,
            "mileage": self.mileage,
            "cost_per_km": self.cost_per_km,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M")
        }


# -------------------------
# ROUTES
# -------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/logs", methods=["GET"])
def get_logs():
    logs = MileageLog.query.order_by(MileageLog.id.desc()).all()
    return jsonify([log.to_dict() for log in logs])


@app.route("/api/logs", methods=["POST"])
def save_log():
    data = request.json

    fuel_type = data["fuel_type"]
    fuel_used = float(data["fuel_used"])
    fuel_price = float(data["fuel_price"])
    petrol_no_distance = data.get("petrol_no_distance", False)

    # Default
    distance = 0
    mileage = 0
    cost_per_km = 0

    if fuel_type == "CNG":
        # CNG always has distance
        distance = float(data["distance"])
        mileage = distance / fuel_used
        cost_per_km = (fuel_used * fuel_price) / distance

    elif fuel_type == "Petrol":
        if not petrol_no_distance:
            # In case someone wants petrol WITH distance
            distance = float(data["distance"])
            mileage = distance / fuel_used
            cost_per_km = (fuel_used * fuel_price) / distance
        else:
            # Petrol warm-up → no distance
            distance = 0
            mileage = 0
            cost_per_km = 0  # cannot be calculated

    new_log = MileageLog(
        fuel_type=fuel_type,
        distance=distance,
        fuel_used=fuel_used,
        fuel_price=fuel_price,
        mileage=mileage,
        cost_per_km=cost_per_km
    )

    db.session.add(new_log)
    db.session.commit()

    return jsonify(new_log.to_dict()), 201


@app.route("/api/overall")
def overall_stats():
    logs = MileageLog.query.all()

    if not logs:
        return jsonify({
            "overall_mileage": 0,
            "overall_cost_per_km": 0
        })

    total_distance = sum(l.distance for l in logs)             # only CNG & petrol-with-distance
    total_cng_fuel = sum(l.fuel_used for l in logs if l.fuel_type == "CNG")
    total_cost = sum(l.fuel_used * l.fuel_price for l in logs)

    # Mileage = only based on CNG distance & fuel
    overall_mileage = total_distance / total_cng_fuel if total_cng_fuel > 0 else 0

    # Total running cost per km = (all fuel costs) / (distance driven)
    overall_cost_per_km = total_cost / total_distance if total_distance > 0 else 0

    return jsonify({
        "overall_mileage": round(overall_mileage, 2),
        "overall_cost_per_km": round(overall_cost_per_km, 2)
    })

@app.route("/api/logs/<int:log_id>", methods=["DELETE"])
def delete_log(log_id):
    log = MileageLog.query.get(log_id)
    if not log:
        return jsonify({"error": "Not found"}), 404

    db.session.delete(log)
    db.session.commit()
    return jsonify({"message": "Deleted"}), 200

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
