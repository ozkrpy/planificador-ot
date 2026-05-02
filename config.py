import os

class Config:
    """Shared base — never instantiated directly."""
    SECRET_KEY          = os.environ.get('SECRET_KEY', 'changeme')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED    = True

class DevelopmentConfig(Config):
    DEBUG    = True
    ENV      = 'development'
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DEV_DATABASE_URL',
        'sqlite:///ot_planning_dev.db'
    )

class StagingConfig(Config):
    DEBUG    = False
    TESTING  = True
    ENV      = 'staging'
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'STAGING_DATABASE_URL',
        'sqlite:///ot_planning_staging.db'
    )

class ProductionConfig(Config):
    DEBUG    = False
    ENV      = 'production'
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///harmony.db'   # change to real DB
    )
    SESSION_COOKIE_SECURE   = True
    SESSION_COOKIE_HTTPONLY = True

config = {
    'development': DevelopmentConfig,
    'staging':     StagingConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig
}