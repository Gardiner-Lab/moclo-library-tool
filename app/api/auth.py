"""
Authentication API endpoints.

This module provides REST API endpoints for:
- User registration (POST /api/auth/register)
- User login (POST /api/auth/login)
- User logout (POST /api/auth/logout)
- Session status check (GET /api/auth/session)

Requirements: 9.1, 9.2, 9.3, 9.6
"""

from flask import Blueprint, request, jsonify, session
from app.services.auth import AuthService
from app.services.backup import backup_all
from functools import wraps
from typing import Callable, Any

# Create blueprint
auth_bp = Blueprint('auth', __name__)


def require_session(f: Callable) -> Callable:
    """
    Decorator to require a valid session for an endpoint.
    
    Returns 401 Unauthorized if session is invalid or missing.
    """
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        session_id = session.get('session_id')
        
        if not session_id or not AuthService.validate_session(session_id):
            return jsonify({
                'error': 'Authentication required'
            }), 401
        
        return f(*args, **kwargs)
    
    return decorated_function


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new user.
    
    Request Body:
        {
            "username": "string",
            "password": "string"
        }
    
    Response (201 Created):
        {
            "user": {
                "id": "string",
                "username": "string",
                "created_at": "ISO8601 timestamp"
            },
            "message": "User registered successfully"
        }
    
    Error Responses:
        400 Bad Request: Missing or invalid fields
        409 Conflict: Username already exists
    
    Requirements: 9.1, 9.2
    """
    try:
        # Parse request body
        data = request.get_json(silent=True)
        
        if data is None:
            return jsonify({
                'error': 'Request body must be JSON'
            }), 400
        
        username = data.get('username')
        password = data.get('password')
        
        # Validate required fields
        if not username:
            return jsonify({
                'error': 'Missing required field: username'
            }), 400
        
        if not password:
            return jsonify({
                'error': 'Missing required field: password'
            }), 400
        
        # Register user
        user_data = AuthService.register(username, password)
        
        return jsonify({
            'user': user_data,
            'message': 'User registered successfully'
        }), 201
        
    except ValueError as e:
        error_msg = str(e)
        
        # Check if it's a duplicate username error
        if 'already exists' in error_msg.lower():
            return jsonify({
                'error': error_msg
            }), 409
        
        # Other validation errors
        return jsonify({
            'error': error_msg
        }), 400
    
    except Exception as e:
        return jsonify({
            'error': 'Internal server error'
        }), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Login and create a session.
    
    Request Body:
        {
            "username": "string",
            "password": "string"
        }
    
    Response (200 OK):
        {
            "user": {
                "id": "string",
                "username": "string",
                "created_at": "ISO8601 timestamp"
            },
            "session_id": "string",
            "expires_at": "ISO8601 timestamp",
            "message": "Login successful"
        }
    
    Error Responses:
        400 Bad Request: Missing fields
        401 Unauthorized: Invalid credentials
    
    Requirements: 9.1, 9.3, 9.4
    """
    try:
        # Parse request body
        data = request.get_json(silent=True)
        
        if data is None:
            return jsonify({
                'error': 'Request body must be JSON'
            }), 400
        
        username = data.get('username')
        password = data.get('password')
        
        # Validate required fields
        if not username or not password:
            return jsonify({
                'error': 'Missing required fields: username and password'
            }), 400
        
        # Authenticate user
        login_data = AuthService.login(username, password)
        
        # Store session ID in Flask session
        session['session_id'] = login_data['session_id']
        session['user_id'] = login_data['user']['id']
        session['username'] = login_data['user']['username']
        session['is_admin'] = login_data['user'].get('is_admin', False)
        
        return jsonify({
            'user': login_data['user'],
            'session_id': login_data['session_id'],
            'expires_at': login_data['expires_at'],
            'message': 'Login successful'
        }), 200
        
    except ValueError as e:
        return jsonify({
            'error': str(e)
        }), 401
    
    except Exception as e:
        return jsonify({
            'error': 'Internal server error'
        }), 500


@auth_bp.route('/logout', methods=['POST'])
@require_session
def logout():
    """
    Logout and terminate the session.
    
    Response (200 OK):
        {
            "message": "Logout successful"
        }
    
    Error Responses:
        401 Unauthorized: No valid session
    
    Requirements: 9.1, 9.6
    """
    try:
        # Get session ID from Flask session
        session_id = session.get('session_id')
        
        # Terminate session
        AuthService.logout(session_id)
        
        # Clear Flask session
        session.clear()
        
        # Back up databases on logout
        backup_all()
        
        return jsonify({
            'message': 'Logout successful'
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error'
        }), 500


@auth_bp.route('/session', methods=['GET'])
def check_session():
    """
    Check current session status.
    
    Response (200 OK) - Valid session:
        {
            "authenticated": true,
            "user": {
                "id": "string",
                "username": "string",
                "created_at": "ISO8601 timestamp"
            },
            "session_id": "string"
        }
    
    Response (200 OK) - No valid session:
        {
            "authenticated": false
        }
    
    Requirements: 9.1, 9.4
    """
    try:
        # Get session ID from Flask session
        session_id = session.get('session_id')
        
        if not session_id:
            return jsonify({
                'authenticated': False
            }), 200
        
        # Validate session
        user = AuthService.get_user_from_session(session_id)
        
        if user is None:
            # Session is invalid or expired
            session.clear()
            return jsonify({
                'authenticated': False
            }), 200
        
        # Session is valid
        return jsonify({
            'authenticated': True,
            'user': user.to_dict(),
            'session_id': session_id
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error'
        }), 500
