import os
import re
from flask import Flask, jsonify, render_template, request, url_for
from flask_jsglue import JSGlue
import itertools

from cs50 import SQL
from helpers import lookup

# configure application
app = Flask(__name__)
JSGlue(app)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# configure CS50 Library to use SQLite database
#db = SQL("sqlite:///mashup.db")
db = SQL("sqlite:///{}".format(os.path.join(os.path.dirname(__file__), "mashup.db")))
@app.route("/")
def index():
    """Render map."""
    if not os.environ.get("API_KEY"):
        raise RuntimeError("API_KEY not set")
    return render_template("index.html", key=os.environ.get("API_KEY"))

@app.route("/articles")
def articles():
    """Look up articles for geo."""
    
    geo = request.args.get("geo")
    if geo:
        return jsonify(lookup(geo))
    else:
        return jsonify([])

@app.route("/search")
def search():
    """Search for places that match query."""

    q = request.args.get("q")
    if search:
        # TODO: Make it work for multiple criteria eg. Cambridge,MA
        qs = q.replace(" ", "").split(",")
        numitems = len(qs)
        
        if numitems == 1:
            # could be one of anything
            postcode = qs[0]
            results = db.execute("SELECT * FROM places WHERE postal_code LIKE :q OR place_name LIKE :q OR admin_name1 LIKE :q OR admin_code1 LIKE :q", q=postcode + "%")
        elif numitems == 2:
            try:
                # last item is postcode, so format is state, postcode
                postcode = int(qs[1]) # this just triggers ValueError if not a number
                postcode = qs[1] + "%"
                state = qs[0]
                results = db.execute("SELECT * FROM places WHERE postal_code LIKE :postcode AND (admin_name1 LIKE :state1 OR admin_code1 = :state2)", postcode=postcode, state1=state + "%", state2=state)
            except ValueError:
                # last items isn't postcode, so format is city, state
                city = qs[0] + "%"
                state = qs[1]
                print(state, len(state))
                if len(state) > 3:
                    results = db.execute("SELECT * FROM places WHERE place_name LIKE :city AND admin_name1 LIKE :state", city=city, state=state + "%")
                else:
                    results = db.execute("SELECT * FROM places WHERE place_name LIKE :city AND admin_code1 = :state", city=city, state=state)
        elif numitems == 3:
            # format is city, state, postcode
            city = qs[0] + "%"
            state = qs[1] + "%"
            postcode = qs[2] + "%"
            
            if len(state) > 3:
                results = db.execute("SELECT * FROM places WHERE place_name LIKE :city AND admin_name1 LIKE :state AND postal_code LIKE :postcode", city=city, state=state + "%", postcode=postcode)
            else:
                results = db.execute("SELECT * FROM places WHERE place_name LIKE :city AND admin_code = :state AND postal_code LIKE :postcode", city=city, state=state, postcode=postcode)
            
        
        return jsonify(results)
    else:
        return jsonify([])

@app.route("/update")
def update():
    """Find up to 10 places within view."""

    # ensure parameters are present
    if not request.args.get("sw"):
        raise RuntimeError("missing sw")
    if not request.args.get("ne"):
        raise RuntimeError("missing ne")

    # ensure parameters are in lat,lng format
    if not re.search("^-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?$", request.args.get("sw")):
        raise RuntimeError("invalid sw")
    if not re.search("^-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?$", request.args.get("ne")):
        raise RuntimeError("invalid ne")

    # explode southwest corner into two variables
    (sw_lat, sw_lng) = [float(s) for s in request.args.get("sw").split(",")]

    # explode northeast corner into two variables
    (ne_lat, ne_lng) = [float(s) for s in request.args.get("ne").split(",")]

    # find 10 cities within view, pseudorandomly chosen if more within view
    if (sw_lng <= ne_lng):

        # doesn't cross the antimeridian
        rows = db.execute("""SELECT * FROM places
            WHERE :sw_lat <= latitude AND latitude <= :ne_lat AND (:sw_lng <= longitude AND longitude <= :ne_lng)
            GROUP BY country_code, place_name, admin_code1
            ORDER BY RANDOM()
            LIMIT 10""",
            sw_lat=sw_lat, ne_lat=ne_lat, sw_lng=sw_lng, ne_lng=ne_lng)

    else:

        # crosses the antimeridian
        rows = db.execute("""SELECT * FROM places
            WHERE :sw_lat <= latitude AND latitude <= :ne_lat AND (:sw_lng <= longitude OR longitude <= :ne_lng)
            GROUP BY country_code, place_name, admin_code1
            ORDER BY RANDOM()
            LIMIT 10""",
            sw_lat=sw_lat, ne_lat=ne_lat, sw_lng=sw_lng, ne_lng=ne_lng)

    # output places as JSON
    return jsonify(rows)
