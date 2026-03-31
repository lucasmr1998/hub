from django.core.management.base import BaseCommand
from apps.sistema.models import ConfiguracaoEmpresa

class Command(BaseCommand):
    help = 'Atualiza o nome da empresa de "Sua Empresa" para "Megalink"'

    def handle(self, *args, **options):
        try:
            # Buscar configurações existentes
            configuracoes = ConfiguracaoEmpresa.objects.all()
            
            if configuracoes.exists():
                self.stdout.write(f"Encontradas {configuracoes.count()} configurações de empresa")
                
                # Atualizar todas as configurações que têm "Sua Empresa" ou "AuroraISP"
                atualizadas = 0
                for config in configuracoes:
                    if config.nome_empresa in ["Sua Empresa", "AuroraISP"]:
                        config.nome_empresa = "Megalink"
                        config.save()
                        atualizadas += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"✅ Configuração ID {config.id} atualizada → Megalink")
                        )
                
                if atualizadas == 0:
                    self.stdout.write(self.style.WARNING("ℹ️ Nenhuma configuração necessitando atualização encontrada"))
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f"🎉 {atualizadas} configurações atualizadas com sucesso!")
                    )
            else:
                self.stdout.write("ℹ️ Nenhuma configuração de empresa encontrada. Criando nova configuração...")
                
                # Criar nova configuração com Megalink
                nova_config = ConfiguracaoEmpresa.objects.create(
                    nome_empresa="Megalink",
                    cor_primaria="#1F3D59",
                    cor_secundaria="#2c5aa0",
                    ativo=True
                )
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Nova configuração criada: {nova_config}")
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Erro ao atualizar configurações: {e}")
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS("✅ Atualização concluída com sucesso!")
        )
