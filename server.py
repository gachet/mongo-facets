from flask import Flask, request, jsonify
from pymongo import MongoClient

app = Flask(__name__, static_folder='client')
client = MongoClient('localhost:27017')
db = client.test
API_ENDPOINT = '/api/v1'

def _get_array_param(param):
    return filter(None, param.split(","))

def _get_facet_borough(cuisines, zipcodes):
    match = {}

    if cuisines:
        match['cuisine'] = {'$in': cuisines}
    if zipcodes:
        match['address.zipcode'] = {'$in': zipcodes}

    pipeline = [
        {'$match': match}
    ] if match else []

    return pipeline + _get_group_pipeline('borough')

def _get_facet_cuisine(boroughs, zipcodes):
    match = {}

    if boroughs:
        match['borough'] = {'$in': boroughs}
    if zipcodes:
        match['address.zipcode'] = {'$in': zipcodes}

    pipeline = [
        {'$match': match}
    ] if match else []

    return pipeline + _get_group_pipeline('cuisine')

def _get_facet_zipcode(boroughs, cuisines):
    match = {}

    if boroughs:
        match['borough'] = {'$in': boroughs}
    if cuisines:
        match['cuisine'] = {'$in': cuisines}

    pipeline = [
        {'$match': match},
    ] if match else []

    return pipeline + _get_group_pipeline('address.zipcode')

def _get_group_pipeline(group_by):
    return [
        {
            '$group': {
                '_id': '$' + group_by,
                'count': {'$sum': 1},
            }
        },
        {
            '$project': {
                '_id': 0,
                'value': '$_id',
                'count': 1,
            }
        },
        {
            '$sort': {'count': -1}
        },
        {
            '$limit': 6,
        }
    ]

# API
@app.route(API_ENDPOINT + "/restaurants")
def restaurants():
    # pagination
    page = int(request.args.get('page', '0'))
    page_size = int(request.args.get('page-size', '50'))
    skip = page * page_size
    limit = min(page_size, 50)

    # filters
    search = request.args.get('search', '')
    boroughs = _get_array_param(request.args.get('boroughs', ''))
    cuisines = _get_array_param(request.args.get('cuisines', ''))
    zipcode = _get_array_param(request.args.get('zipcodes', ''))

    match = {}
    if search:
        match['$text'] = {'$search': search}
    if boroughs:
        match['borough'] = {'$in': boroughs}
    if cuisines:
        match['cuisine'] = {'$in': cuisines}
    if zipcode:
        match['address.zipcode'] = {'$in': zipcode}

    pipeline = [{
        '$match': match
    }] if match else []

    pipeline += [{
        '$facet': {
            'restaurants': [
                {'$skip': skip},
                {'$limit': limit}
            ],
            'count': [
                {'$count': 'total'}
            ],
        }
    }]

    result = list(db.restaurants.aggregate(pipeline)).pop()

    for restaurant in result['restaurants']: # remove _id, is an ObjectId and is not serializable
        restaurant.pop('_id')
    result['count'] = result['count'].pop()['total'] if result['count'] else 0
    return jsonify(result)

@app.route(API_ENDPOINT + "/restaurants/facets")
def restaurants_and_facets():
    # filters
    search = request.args.get('search', '')
    boroughs = _get_array_param(request.args.get('boroughs', ''))
    cuisines = _get_array_param(request.args.get('cuisines', ''))
    zipcodes = _get_array_param(request.args.get('zipcodes', ''))

    pipeline = [{
        '$match': {'$text': {'$search': search}}
    }] if search else []

    pipeline += [{
        '$facet': {
            'borough': _get_facet_borough(cuisines, zipcodes),
            'cuisine': _get_facet_cuisine(boroughs, zipcodes),
            'zipcode': _get_facet_zipcode(boroughs, cuisines),
        }
    }]

    restaurant_facets = list(db.restaurants.aggregate(pipeline)).pop()

    return jsonify(restaurant_facets)

@app.route(API_ENDPOINT + "/restaurants/count")
def restaurants_count():
    restaurants_count = db.restaurants.find().count()
    return jsonify(restaurants_count)

# Statics
@app.route('/')
def root():
  return app.send_static_file('index.html')

@app.route('/<path:path>')
def static_proxy(path):
  # send_static_file will guess the correct MIME type
  return app.send_static_file(path)

# run the application without flask-cli
if __name__ == "__main__":
    app.run(debug=True)