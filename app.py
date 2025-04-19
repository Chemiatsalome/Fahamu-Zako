from flask import Flask, render_template, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from models import db  # Import db from models/__init__.py
from models.models import User  # Import models
import dotenv


from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests

app.config.from_object('config.Config')

db.init_app(app)
migrate = Migrate(app, db)

# Import models to register them
with app.app_context():
    from models.models import *

# Import routes
from routes.authroutes import Login_bp, signup_bp
from AI_model.modelIntegration import chat_bp
from routes.approutes import approutes_bp

# Register Blueprints (modular routes)
app.register_blueprint(Login_bp)
app.register_blueprint(signup_bp)
app.register_blueprint(approutes_bp)
app.register_blueprint(chat_bp, url_prefix="/chat")  # Register the blueprint

# Use waitress to serve the app
# from waitress import serve

# if __name__ == "__main__":
#     serve(app, host='0.0.0.0', port=8000)
if __name__ == '__main__':
    app.run(debug=True)