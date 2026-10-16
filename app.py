from flask import (
    Flask,
    render_template,
    request,
    jsonify
)

from agents.trip_agent import TripAgent


app = Flask(__name__)

trip_agent = TripAgent()


@app.route("/")
def home():
    """
    Main UI page
    """
    return render_template("index.html")


@app.route("/health")
def health():
    """
    Health check endpoint
    """
    return jsonify({
        "status": "ok",
        "service": "TripPilot"
    })


@app.route("/chat", methods=["POST"])
def chat():

    try:

        data = request.get_json()

        message = data.get(
            "message",
            ""
        )

        if not message:

            return jsonify({
                "error":
                "Message cannot be empty"
            }), 400

        booking_proposal = data.get("booking_proposal")
        if booking_proposal is None:
            result = trip_agent.run(message)
        else:
            result = trip_agent.run(
                message,
                booking_proposal=booking_proposal
            )

        return jsonify(result)

    except ValueError as e:

        print(
            "CHAT VALIDATION ERROR:",
            str(e)
        )

        return jsonify({

            "agent_steps": [
                "Request failed validation"
            ],

            "recommendation":
                f"Error: {str(e)}",

            "flights": [],

            "event": None,

            "monitor_result": None,

            "replan_result": None

        }), 400

    except Exception as e:

        print(
            "CHAT ERROR:",
            str(e)
        )

        return jsonify({

            "agent_steps": [
                "Request failed"
            ],

            "recommendation":
                f"Error: {str(e)}",

            "flights": [],

            "event": None,

            "monitor_result": None,

            "replan_result": None

        }), 500


@app.route(
    "/simulate-disruption",
    methods=["POST"]
)
def simulate_disruption():

    try:

        data = request.get_json()

        trip = data.get(
            "trip",
            {}
        )

        scenario = data.get(
            "scenario",
            "delay"
        )

        event = {

            "type":
                "FLIGHT_DELAY",

            "severity":
                "HIGH",

            "delay_hours":
                6,

            "message":
                "Flight delayed by 6 hours"
        }

        if scenario == "cancel":

            event = {

                "type":
                    "FLIGHT_CANCELLED",

                "severity":
                    "HIGH",

                "message":
                    "Flight cancelled"
            }

        monitor_result = (
            trip_agent.monitor.analyse(
                trip,
                event
            )
        )

        replan_result = (
            trip_agent.replanner.replan(
                trip,
                event
            )
        )

        return jsonify({

            "event":
                event,

            "monitor_result":
                monitor_result,

            "replan_result":
                replan_result
        })

    except Exception as e:

        print(
            "SIMULATE ERROR:",
            str(e)
        )

        return jsonify({
            "error": str(e)
        }), 500

@app.route("/demo")
def demo():

    """
    Simple demo payload
    """

    return jsonify({

        "message":
            "Try asking: "
            "'I need a flight from Hong Kong "
            "to London on 15 Nov 2026'"

    })


if __name__ == "__main__":

    print(
        "\n================================="
    )

    print(
        "TripPilot AI Agent Started"
    )

    print(
        "URL: http://localhost:5000"
    )

    print(
        "=================================\n"
    )

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )