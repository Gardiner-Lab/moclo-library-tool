"""
Main Flask application entry point.
"""

from flask import Flask, render_template, session, redirect, url_for
from flask_cors import CORS
import os
from app.models import initialize_database
from app.models.parts_database import initialize_parts_database
from app.init_db import initialize_with_seed_data

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['DATABASE_PATH'] = os.environ.get('DATABASE_PATH', '/data/moclo.db')
    
    # Enable template auto-reload for development
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    
    # Initialize database with optional seed data
    seed_file = os.environ.get('SEED_DATA_FILE')
    if seed_file or os.path.exists('/data/seed_data.json'):
        # Use initialization script with seed data support
        initialize_with_seed_data(
            app.config['DATABASE_PATH'],
            seed_file or '/data/seed_data.json'
        )
    else:
        # Standard initialization without seed data
        initialize_database(app.config['DATABASE_PATH'])
        # Also initialize the separate parts database
        parts_db_path = os.environ.get('PARTS_DATABASE_PATH', '/data/parts.db')
        initialize_parts_database(parts_db_path)
        # Ensure default admin exists
        from app.init_db import _ensure_default_admin, _ensure_demo_backbones
        _ensure_default_admin()
        _ensure_demo_backbones()
    
    # Enable CORS with credentials support
    CORS(app, supports_credentials=True)
    
    # Register blueprints
    from app.api import auth_bp, parts_bp, cassettes_bp, visualize_bp, backbones_bp, plasmids_bp, admin_bp
    from app.api.user_dashboard import user_dashboard_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(parts_bp, url_prefix='/api/parts')
    app.register_blueprint(cassettes_bp, url_prefix='/api/cassettes')
    app.register_blueprint(visualize_bp, url_prefix='/api/visualize')
    app.register_blueprint(backbones_bp, url_prefix='/api/backbones')
    app.register_blueprint(plasmids_bp, url_prefix='/api/plasmids')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(user_dashboard_bp, url_prefix='/api/me')
    
    # Web interface routes
    @app.route('/')
    def index():
        """Home page - redirect to protocol if logged in, otherwise to login."""
        if 'user_id' in session:
            return redirect(url_for('protocol_page'))
        return redirect(url_for('login_page'))
    
    @app.route('/login')
    def login_page():
        """Login page."""
        if 'user_id' in session:
            return redirect(url_for('parts_page'))
        return render_template('login.html')
    
    @app.route('/register')
    def register_page():
        """Registration page."""
        if 'user_id' in session:
            return redirect(url_for('parts_page'))
        return render_template('register.html')
    
    @app.route('/logout')
    def logout_page():
        """Logout - clear session and redirect to login."""
        session.clear()
        return redirect(url_for('login_page'))
    
    @app.route('/parts')
    def parts_page():
        """Parts browser page."""
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return render_template('parts.html')
    
    @app.route('/cassettes')
    def cassettes_page():
        """Cassettes management page."""
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return render_template('cassettes.html')
    
    @app.route('/assembly')
    def assembly_page():
        """Cassette assembly page."""
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return render_template('assembly.html')
    
    @app.route('/upload')
    def upload_page():
        """Part upload page."""
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return render_template('upload.html')
    
    @app.route('/backbones')
    def backbones_page():
        """Backbones management page."""
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return render_template('backbones.html')
    
    @app.route('/plasmids')
    def plasmids_page():
        """Plasmids listing page."""
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return render_template('plasmids.html')
    
    @app.route('/plasmid-assembly')
    def plasmid_assembly_page():
        """Plasmid assembly page."""
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return render_template('plasmid_assembly.html')
    
    @app.route('/dashboard')
    def dashboard_page():
        """User dashboard."""
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return render_template('dashboard.html')

    @app.route('/admin')
    def admin_page():
        """Admin dashboard."""
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return render_template('admin.html')

    @app.route('/protocol')
    def protocol_page():
        """MoClo protocol guide page."""
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return render_template('protocol.html')
    
    @app.route('/annotation-guide')
    def annotation_guide():
        """GenBank annotation best practices guide."""
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return render_template('annotation_guide.html')
    
    @app.route('/test-buttons')
    def test_buttons():
        """Test page to verify buttons are visible."""
        return render_template('test_buttons.html')
    
    @app.route('/health')
    def health():
        """Health check endpoint."""
        return {'status': 'healthy'}
    
    return app

# Create the app instance
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
