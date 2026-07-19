from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='RegraValidacao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question_id', models.SlugField(help_text='Identificador único enviado pelo Matrix (ex: coleta_cpf)', max_length=80, unique=True, verbose_name='ID da pergunta')),
                ('pergunta_padrao', models.TextField(help_text='Texto da pergunta no Matrix (também usado pra matching textual quando question_id não vem)', verbose_name='Pergunta padrão')),
                ('ordem', models.IntegerField(default=0, help_text='Ordem sugerida no fluxo (apenas informativo)')),
                ('descricao', models.CharField(blank=True, help_text='Descrição curta do propósito da regra', max_length=200)),
                ('ativo', models.BooleanField(default=True)),
                ('extractor_tipo', models.CharField(
                    choices=[
                        ('cpf', 'CPF (regex + dígito verificador)'),
                        ('cep', 'CEP (regex + ViaCEP + cobertura)'),
                        ('nome', 'Nome completo'),
                        ('telefone', 'Telefone'),
                        ('data_nascimento', 'Data nascimento (valida >=18)'),
                        ('email', 'E-mail'),
                        ('numero', 'Número (residência, etc)'),
                        ('opcao', 'Opção de menu (1, 2, 3...)'),
                        ('confirmacao', 'Sim/Não'),
                        ('imagem', 'URL de imagem'),
                        ('texto_livre', 'Texto livre (IA decide)'),
                        ('livre', 'Sem validação (sempre aceita)'),
                    ],
                    default='texto_livre', max_length=20, verbose_name='Tipo de validador',
                )),
                ('extractor_config', models.JSONField(blank=True, default=dict, help_text='JSON com config extra. Ex: {"opcoes": {"1": "manha", "2": "tarde"}} pra opcao', verbose_name='Config do validador')),
                ('instrucoes_ia', models.TextField(blank=True, help_text='Texto adicional pro system prompt quando cai no fallback IA', verbose_name='Instruções extras pra IA')),
                ('permite_pular', models.BooleanField(default=False, help_text='Cliente pode dizer "não" / "depois" e seguir')),
                ('max_tentativas', models.IntegerField(default=3)),
                ('campo_lead_atualizar', models.CharField(blank=True, help_text='Nome do campo no LeadProspecto (ex: cpf_cnpj). Recebe o valor de extracted_data.', max_length=60, verbose_name='Campo do lead a atualizar')),
                ('status_api_apos_sucesso', models.CharField(blank=True, help_text='Ex: aguardando_assinatura, em_instalacao, pendente. Em branco = não muda.', max_length=40, verbose_name='status_api após sucesso')),
                ('tags_adicionar', models.JSONField(blank=True, default=list, help_text='Lista de strings: ["Comercial", "Endereço"]', verbose_name='Tags a adicionar')),
                ('tags_remover', models.JSONField(blank=True, default=list)),
                ('historico_status_apos_sucesso', models.CharField(blank=True, help_text='Ex: fluxo_inicializado, fluxo_finalizado. Em branco = não registra.', max_length=40, verbose_name='Status do histórico após sucesso')),
                ('historico_observacoes_template', models.TextField(blank=True, help_text='Variáveis disponíveis: {question}, {answer}, {extracted}', verbose_name='Template das observações do histórico')),
                ('descricao_imagem', models.CharField(blank=True, help_text='Se extractor=imagem: ex: selfie_com_doc, frente_doc, verso_doc', max_length=50, verbose_name='Descrição da imagem')),
                ('msg_sucesso', models.TextField(blank=True, help_text='Ex: "Anotei seu CPF!" — pode ter {extracted}', verbose_name='Mensagem de sucesso (padrão pro cliente)')),
                ('msg_erro', models.TextField(blank=True, help_text='Ex: "CPF inválido, pode conferir?"', verbose_name='Mensagem de erro')),
                ('msg_max_tentativas', models.TextField(blank=True, verbose_name='Mensagem após exceder tentativas')),
                ('forcar_transbordo_apos_max', models.BooleanField(default=False, verbose_name='Forçar transbordo após máximo de tentativas')),
                ('data_criacao', models.DateTimeField(auto_now_add=True)),
                ('data_atualizacao', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Regra de Validação',
                'verbose_name_plural': 'Regras de Validação',
                'ordering': ['ordem', 'question_id'],
            },
        ),
    ]
