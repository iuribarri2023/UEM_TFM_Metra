"""App factory - DB, transactions and errors, no legacy Phase 3 routes."""
import os,logging
from pathlib import Path
from flask import Flask, g, jsonify, request, Response, make_response
from sqlalchemy import create_engine,text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError,SQLAlchemyError
from werkzeug.exceptions import HTTPException
from .api import api,ApiError
from .catalogue import TemplateProjectionIntegrityError

def create_app(overrides=None):
    app=Flask(__name__)
    app.config.update(DATABASE_URL=os.getenv('DATABASE_URL','postgresql+psycopg://marketplace:marketplace@localhost:5432/marketplace'),
        JWT_SECRET=os.getenv('JWT_SECRET',''), ASSET_DIR=os.getenv('ASSET_DIR','/data/assets'),
        MAX_CONTENT_LENGTH=int(os.getenv('MAX_UPLOAD_BYTES','52428800')),
        COOKIE_SECURE=os.getenv('COOKIE_SECURE','1')=='1', BRAND=os.getenv('BRAND','METRA'))
    if overrides:app.config.update(overrides)
    if (len(app.config['JWT_SECRET'])<32 or app.config['JWT_SECRET'].startswith('CHANGE_ME_')) and not app.config.get('TESTING'):
        raise RuntimeError('JWT_SECRET aleatorio de al menos 32 caracteres obligatorio')
    engine=create_engine(app.config['DATABASE_URL'],pool_pre_ping=True,hide_parameters=True)
    app.extensions['engine']=engine
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    @app.before_request
    def session():
        g.db=factory();g.created_files=[]
    @app.after_request
    def transaction(response):
        db=getattr(g,'db',None)
        if db:
            try:
                if response.status_code<400:db.commit()
                else:db.rollback()
            except IntegrityError:
                db.rollback()
                for f in g.created_files:f.unlink(missing_ok=True)
                return make_response(jsonify({'error':{'code':'CONFLICT','message':'Conflicto de integridad referencial','details':[]}}),409)
            except Exception:
                db.rollback()
                for f in g.created_files:f.unlink(missing_ok=True)
                app.logger.exception('Transaction failure')
                return make_response(jsonify({'error':{'code':'INTERNAL','message':'Error interno','details':[]}}),500)
            if response.status_code>=400:
                for f in g.created_files:f.unlink(missing_ok=True)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Content-Security-Policy']="default-src 'none'; frame-ancestors 'none'" if request.path.startswith('/api/') else "default-src 'self'"
        return response
    @app.teardown_request
    def close(exc):
        db=getattr(g,'db',None)
        if db:
            if exc:db.rollback()
            db.close()
    @app.errorhandler(ApiError)
    def handle_api(e):return jsonify({'error':{'code':e.code,'message':e.message,'details':e.details}}),e.status
    @app.errorhandler(TemplateProjectionIntegrityError)
    def handle_template(e):
        return jsonify({'error':{'code':'TEMPLATE_INTEGRITY','message':str(e),'details':[]}}),409
    @app.errorhandler(HTTPException)
    def handle_http(e):
        code='METHOD_NOT_ALLOWED' if e.code==405 else 'HTTP_ERROR'
        return jsonify({'error':{'code':code,'message':e.description,'details':[]}}),e.code
    @app.errorhandler(Exception)
    def unexpected(e):
        app.logger.exception('Request failure')
        return make_response(jsonify({'error':{'code':'INTERNAL','message':'Error interno','details':[]}}),500)
    @app.get('/health')
    def health():
        with engine.connect() as conn:conn.execute(text('SELECT 1'))
        return jsonify({'status':'ok'})
    @app.get('/ready')
    def ready():
        from .readiness import report
        try:
            with factory() as db:result=report(db,app.config['ASSET_DIR'])
        except SQLAlchemyError:
            result={'state':'BLOCKED','schema_ready':False}
        return jsonify(result),503 if result['state']=='BLOCKED' else 200
    @app.get('/api/v1/openapi.json')
    def openapi():
        import json
        return jsonify(json.loads((Path(__file__).parent.parent/'openapi.json').read_text()))
    app.register_blueprint(api)
    # In-process limiter fits single-worker academic deployment; shared Redis is advised for scale.
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address
        lim=Limiter(get_remote_address,app=app,default_limits=['250 per hour'],storage_uri=os.getenv('RATELIMIT_STORAGE_URI','memory://'))
        app.view_functions['api_v1.login']=lim.limit('10 per minute')(app.view_functions['api_v1.login'])
        app.view_functions['api_v1.register']=lim.limit('5 per minute')(app.view_functions['api_v1.register'])
        app.view_functions['api_v1.accept_invitation']=lim.limit('8 per minute')(app.view_functions['api_v1.accept_invitation'])
        app.view_functions['api_v1.upload_revision_asset']=lim.limit('20 per hour')(app.view_functions['api_v1.upload_revision_asset'])
        app.view_functions['api_v1.generic_upload']=lim.limit('20 per hour')(app.view_functions['api_v1.generic_upload'])
    except ImportError:
        if not app.config.get('TESTING'):raise RuntimeError('flask-limiter requerido para ejecución')
    return app
