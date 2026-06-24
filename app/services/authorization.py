"""
Authorization middleware for protecting routes and enforcing user isolation.

This module provides:
- Decorator to require authentication for protected routes
- Function to check cassette ownership
- User isolation for cassette access

Requirements: 8.2, 8.3
"""

from functools import wraps
from typing import Optional, Callable, Any
from flask import request, jsonify, session
from app.services.auth import AuthService
from app.models.cassette import Cassette
from app.models.user import User


def require_auth(f: Callable) -> Callable:
    """
    Decorator to require authentication for protected routes.
    
    This decorator checks for a valid session in Flask's session object
    or in the request headers (X-Session-ID). If the session is invalid
    or missing, it returns a 401 Unauthorized response.
    
    The authenticated user is passed to the wrapped function as the
    first argument after self (if present).
    
    Usage:
        @app.route('/api/protected')
        @require_auth
        def protected_route(user):
            return jsonify({'message': f'Hello {user.username}'})
    
    Args:
        f: The route handler function to protect
        
    Returns:
        Wrapped function that enforces authentication
        
    Requirements: 8.2, 8.3
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Try to get session ID from Flask session first, then from header
        session_id = session.get('session_id')
        if not session_id:
            session_id = request.headers.get('X-Session-ID')
        
        if not session_id:
            return jsonify({
                'error': 'Authentication required',
                'message': 'No session ID provided'
            }), 401
        
        # Validate session and get user
        user = AuthService.get_user_from_session(session_id)
        
        if user is None:
            return jsonify({
                'error': 'Authentication required',
                'message': 'Invalid or expired session'
            }), 401
        
        # Pass the authenticated user to the route handler
        return f(user, *args, **kwargs)
    
    return decorated_function


def check_cassette_ownership(cassette_id: str, user_id: str) -> tuple[bool, Optional[str]]:
    """
    Check if a user owns a specific cassette or if it's a system cassette (read-only).
    
    This function verifies that the cassette exists and that the
    requesting user is the owner of the cassette, or that it's a system
    cassette (which all users can view but not modify).
    
    Args:
        cassette_id: ID of the cassette to check
        user_id: ID of the user requesting access
        
    Returns:
        Tuple of (is_owner, error_message):
        - (True, None) if user owns the cassette or it's a system cassette
        - (False, error_message) if cassette not found or user doesn't own it
        
    Requirements: 8.2, 8.3
    """
    # Retrieve the cassette
    cassette = Cassette.get_by_id(cassette_id)
    
    if cassette is None:
        return False, f"Cassette {cassette_id} not found"
    
    # Check if user owns the cassette
    if cassette.owner_id == user_id:
        return True, None
    
    # Check if it's a system cassette (shared example)
    system_user = User.get_by_username('system')
    if system_user and cassette.owner_id == system_user.id:
        return True, None  # Allow read access to system cassettes
    
    return False, "Access denied to cassette"


def require_cassette_ownership(f: Callable) -> Callable:
    """
    Decorator to require cassette ownership for protected routes.
    
    This decorator combines authentication with cassette ownership checking.
    It expects the route to have a 'cassette_id' parameter (either in the
    URL path or query parameters).
    
    The authenticated user and cassette are passed to the wrapped function.
    
    Usage:
        @app.route('/api/cassettes/<cassette_id>')
        @require_cassette_ownership
        def get_cassette(user, cassette, cassette_id):
            return jsonify(cassette.to_dict())
    
    Args:
        f: The route handler function to protect
        
    Returns:
        Wrapped function that enforces authentication and ownership
        
    Requirements: 8.2, 8.3
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First, check authentication - try Flask session first, then header
        session_id = session.get('session_id')
        if not session_id:
            session_id = request.headers.get('X-Session-ID')
        
        if not session_id:
            return jsonify({
                'error': 'Authentication required',
                'message': 'No session ID provided'
            }), 401
        
        # Validate session and get user
        user = AuthService.get_user_from_session(session_id)
        
        if user is None:
            return jsonify({
                'error': 'Authentication required',
                'message': 'Invalid or expired session'
            }), 401
        
        # Get cassette_id from kwargs (URL parameters)
        cassette_id = kwargs.get('cassette_id')
        
        if not cassette_id:
            return jsonify({
                'error': 'Bad request',
                'message': 'Cassette ID is required'
            }), 400
        
        # Check ownership
        is_owner, error_message = check_cassette_ownership(cassette_id, user.id)
        
        if not is_owner:
            if "not found" in error_message:
                return jsonify({
                    'error': 'Not found',
                    'message': error_message
                }), 404
            else:
                return jsonify({
                    'error': 'Forbidden',
                    'message': error_message
                }), 403
        
        # Get the cassette and pass it to the handler
        cassette = Cassette.get_by_id(cassette_id)
        
        # Pass user and cassette to the route handler
        return f(user, cassette, *args, **kwargs)
    
    return decorated_function


def get_user_cassettes(user_id: str) -> list[Cassette]:
    """
    Get all cassettes owned by a specific user.
    
    This function enforces user isolation by only returning cassettes
    that belong to the specified user.
    
    Args:
        user_id: ID of the user
        
    Returns:
        List of Cassette instances owned by the user
        
    Requirements: 8.2, 8.3
    """
    return Cassette.get_by_owner(user_id)


def can_access_cassette(cassette_id: str, user_id: str) -> bool:
    """
    Check if a user can access a specific cassette.
    
    This is a convenience function that returns a boolean indicating
    whether the user has access to the cassette.
    
    Args:
        cassette_id: ID of the cassette
        user_id: ID of the user
        
    Returns:
        True if user can access the cassette, False otherwise
        
    Requirements: 8.2, 8.3
    """
    is_owner, _ = check_cassette_ownership(cassette_id, user_id)
    return is_owner
