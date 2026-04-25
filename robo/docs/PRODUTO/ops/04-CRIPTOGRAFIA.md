# Criptografia de credenciais

Tokens de API, senhas e secrets de integracao sao guardados criptografados no banco via `apps.sistema.encrypted_fields.EncryptedCharField` / `EncryptedTextField` (Fernet AES-128-CBC).

## Como funciona

```
Usuario cola token "abc123" no painel de integracoes
    ↓
EncryptedCharField.get_prep_value encripta com Fernet(_get_key())
    ↓
Banco guarda "gAAAA..." (ciphertext base64)
    ↓
Hubtrix le, EncryptedCharField.from_db_value decripta com Fernet(_get_key())
    ↓
Service usa "abc123" pra chamar API externa
```

A chave Fernet e derivada de `settings.SECRET_KEY` via SHA256 + base64. Nao tem chave separada.

## Garantias atuais

1. `apps/sistema/apps.py::SistemaConfig.ready` falha o boot se `SECRET_KEY` nao estiver setada ou for default em producao (impede que tokens sejam encriptados com chave que nao persiste).
2. `tests/test_encrypted_fields.py` valida o ciclo encrypt/decrypt entre processos diferentes (subprocess).
3. `from_db_value` retorna `None` em caso de falha (logando ERROR) — nao mascara o problema retornando ciphertext bruto.

## Rotacao de SECRET_KEY (procedimento manual)

**Quando fazer:** vazamento confirmado da SECRET_KEY, ou mudanca de politica de seguranca.

**Cuidado:** trocar a SECRET_KEY torna **todos** os tokens encriptados ilegiveis ate serem re-encriptados. Equivale a invalidar todas as integracoes ativas.

**Procedimento:**

1. **Janela de manutencao** programada (1-2h, dependendo do volume).
2. Levantar **lista de tokens em texto puro** ANTES da rotacao:
   ```python
   from apps.integracoes.models import IntegracaoAPI
   tokens_backup = {
       i.pk: {'access_token': i.access_token, 'client_secret': i.client_secret, 'password': i.password}
       for i in IntegracaoAPI.objects.all()
   }
   # Salvar tokens_backup em arquivo TEMPORARIO seguro fora do repo.
   ```
3. **Trocar SECRET_KEY** no `.env` da producao + reiniciar containers.
4. **Re-salvar tokens** com a nova chave:
   ```python
   for pk, fields in tokens_backup.items():
       IntegracaoAPI.objects.filter(pk=pk).update(**fields)
   ```
5. **Validar** rodando management command de smoke test (a implementar).
6. **Deletar** o arquivo de backup temporario.
7. Notificar todos os tenants que houve manutencao (mesmo se tudo correr bem).

**Se algo der errado** durante a rotacao: tokens viram lixo permanente. Cada tenant precisa recadastrar via UI — nao tem como reverter.

## Diagnostico rapido

**Sintoma:** API externa responde 401/403 mesmo com credencial recem-cadastrada.

**Verificacao:**
```python
from apps.integracoes.models import IntegracaoAPI
i = IntegracaoAPI.objects.get(pk=X)
print(i.access_token)  # se comecar com "gAAAA" ou for None, decrypt falhou
```

**Logs esperados em caso de falha:**
```
ERROR encrypted_fields EncryptedCharField: falha de decrypt em integracoes.IntegracaoAPI.access_token. Provavel: SECRET_KEY mudou...
```

**Recuperacao:** se o decrypt esta falhando consistentemente, ver se SECRET_KEY mudou. Se sim, restaurar SECRET_KEY anterior OU recadastrar todos os tokens afetados.

## Backlog

- [ ] Botao "testar conexao" no painel de integracoes (verificacao instantanea ao salvar)
- [ ] Daily smoke test de todas as `IntegracaoAPI` ativas (alerta no painel quando alguma quebra)
- [ ] Migrar SECRET_KEY pra Vault/AWS Secrets Manager quando volume justificar
