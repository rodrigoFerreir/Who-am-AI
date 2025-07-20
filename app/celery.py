import os
from celery import Celery

# Define o módulo de configurações padrão do Django para o programa 'celery'.
# Isso evita que você tenha que configurar a variável de ambiente CELERY_SETTINGS_MODULE.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

# Cria uma instância da aplicação Celery
# O nome 'app' é o nome do seu projeto Django.
app = Celery("app")

# Carrega as configurações do Celery a partir das configurações do Django.
# Isso significa que todas as suas configurações CELERY_ no settings.py serão usadas.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-descobre as tarefas em todos os aplicativos Django registrados.
# Isso procurará por arquivos tasks.py dentro de cada aplicativo em INSTALLED_APPS.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
