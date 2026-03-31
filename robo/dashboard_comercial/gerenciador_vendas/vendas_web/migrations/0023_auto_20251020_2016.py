from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('vendas_web', '0022_delete_userprofile'),
    ]

    # A migração original adicionava a coluna 'telefone' via SQL direto:
    # ALTER TABLE auth_user ADD COLUMN telefone VARCHAR(20) NULL;
    # Porém, como essa coluna já existe no banco, isso gerava erro de
    # "duplicate column name: telefone" ao migrar para SQLite.
    #
    # Para evitar o erro e manter o histórico de migrações consistente,
    # deixamos esta migração vazia (no-op).
    operations = []