from flask import Flask, request, jsonify, Response,  make_response
from flask_restful import Api, Resource
from pymongo import MongoClient
from datetime import datetime
from flasgger import Swagger
import json

app = Flask(__name__)
api = Api(app)
swagger = Swagger(app)


client = MongoClient('mongodb://localhost:27017/')
db = client.following_system


def add_user_if_not_exists(user_id):
    if not db.users.find_one({'_id': user_id}):
        db.users.insert_one({
            '_id': user_id,
            'username': f'user_{user_id}',
            'followers': [],
            'following': [],
            'last_follow_date': None,
            'follow_count': 0
        })

def get_current_date_str():
    return datetime.utcnow().date().isoformat()

class FollowAPI(Resource):
    def post(self):
        """
        Follow a user
        ---
        parameters:
          - name: body
            in: body
            required: True
            schema:
              type: object
              required:
                - follower_id
                - followee_id
              properties:
                follower_id:
                  type: string
                followee_id:
                  type: string
        responses:
          200:
            description: Followed successfully
          400:
            description: Bad request
          415:
            description: Unsupported media type
        """
        if request.content_type != 'application/json':
            return jsonify({'error': 'Content-Type must be application/json'}), 415

        data = request.get_json()
        follower_id = data.get('follower_id')
        followee_id = data.get('followee_id')

        if not follower_id or not followee_id:
            return jsonify({'error': 'Missing follower_id or followee_id'}), 400

        
        add_user_if_not_exists(follower_id)
        add_user_if_not_exists(followee_id)

        follower = db.users.find_one({'_id':follower_id})
        followee = db.users.find_one({'_id': followee_id})

        if followee_id in follower.get('following', []):
            return jsonify({'error': 'Already following'}), 400

        current_date_str = get_current_date_str()

        if followee.get('last_follow_date') != current_date_str:
            followee['follow_count'] = 0

        db.users.update_one(
            {'_id': followee_id},
            {
                '$addToSet': {'followers': follower_id},
                '$set': {'last_follow_date': current_date_str},
                '$inc': {'follow_count': 1}
            }
        )

        db.users.update_one(
            {'_id': follower_id},
            {'$addToSet': {'following': followee_id}}
        )

       
        return make_response(jsonify({'message': 'Followed successfully'}), 200)

class UnfollowAPI(Resource):
    def post(self):
        """
        Unfollow a user
        ---
        parameters:
          - name: body
            in: body
            required: True
            schema:
              type: object
              required:
                - follower_id
                - followee_id
              properties:
                follower_id:
                  type: string
                followee_id:
                  type: string
        responses:
          200:
            description: Unfollowed successfully
          400:
            description: Bad request
          415:
            description: Unsupported media type
        """
        if request.content_type != 'application/json':
            return jsonify({'error': 'Content-Type must be application/json'}), 415

        data = request.get_json()
        follower_id = data.get('follower_id')
        followee_id = data.get('followee_id')

        if not follower_id or not followee_id:
            return jsonify({'error': 'Missing follower_id or followee_id'}), 400

      
        add_user_if_not_exists(follower_id)
        add_user_if_not_exists(followee_id)

        follower = db.users.find_one({'_id': follower_id})
        followee = db.users.find_one({'_id': followee_id})

        db.users.update_one(
            {'_id': follower_id},
            {'$pull': {'following': followee_id}}
        )
        db.users.update_one(
            {'_id': followee_id},
            {'$pull': {'followers': follower_id}}
        )
        db.users.update_one(
        {'_id': followee_id},
        {
            '$inc': {'follow_count': -1}
        }
    )
    

        return make_response(jsonify({'message': 'Unfollowed successfully'}), 200)
        

class FollowersCountAPI(Resource):
    def post(self):
        """
        Get followers count of a user
        ---
        parameters:
          - name: body
            in: body
            required: True
            schema:
              type: object
              required:
                - user_id
              properties:
                user_id:
                  type: string
        responses:
          200:
            description: Followers count
          404:
            description: User not found
        """
        
        data = request.get_json()
        user_id = data.get('user_id')
        user = db.users.find_one({'_id': user_id})

        if not user:
            return jsonify({'error': 'User not found'}), 404

        
        return make_response(jsonify({'followers_count': user['follow_count']}), 200)

class CommonFollowersAPI(Resource):
    def post(self):
        """
        Get common followers of two users
        ---
        parameters:
          - name: body
            in: body
            required: True
            schema:
              type: object
              required:
                - user1_id
                - user2_id
              properties:
                user1_id:
                  type: string
                user2_id:
                  type: string
        responses:
          200:
            description: Common followers
          400:
            description: Bad request
          404:
            description: User not found
        """
        
        data = request.get_json()
        user1_id = data.get('user1_id')
        user2_id = data.get('user2_id')
        if not user1_id or not user2_id:
            return jsonify({'error': 'Missing user1_id or user2_id'}), 400

        user1 = db.users.find_one({'_id': user1_id})
        user2 = db.users.find_one({'_id': user2_id})

        if not user1 or not user2:
            return jsonify({'error': 'User not found'}), 404

        followers_user1 = set(user1.get('followers', []))
        followers_user2 = set(user2.get('followers', []))

        common_followers_ids = followers_user1.intersection(followers_user2)
        common_followers = list(db.users.find({'_id': {'$in': list(common_followers_ids)}}))

        result = [{'id': str(f['_id']), 'username': f['username']} for f in common_followers]
        return make_response(jsonify(result), 200)


class GetAllUsersAPI(Resource):
    def get(self):
        """
        Get all users
        ---
        responses:
          200:
            description: A list of all users
        """
        users = list(db.users.find())
        result = []

        for user in users:
            user_info = {
                'id': str(user['_id']),
                'username': user['username'],
                'followers': [str(f) for f in user.get('followers', [])],
                'following': [str(f) for f in user.get('following', [])],
                'last_follow_date': user.get('last_follow_date'),
                'follow_count': user.get('follow_count', 0)
            }
            result.append(user_info)

        
        return make_response(jsonify(result), 200)



api.add_resource(FollowAPI, '/follow')
api.add_resource(UnfollowAPI, '/unfollow')
api.add_resource(FollowersCountAPI, '/followers')
api.add_resource(CommonFollowersAPI, '/common_followers')
api.add_resource(GetAllUsersAPI, '/users')

if __name__ == '__main__':
    app.run(debug=True)
