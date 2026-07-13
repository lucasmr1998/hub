from django.contrib import admin

from .models import Deck, Slide, SlideBloco


class SlideInline(admin.TabularInline):
    model = Slide
    extra = 0
    fields = ('ordem', 'titulo')
    readonly_fields = ('criado_em',)


class SlideBlocoInline(admin.TabularInline):
    model = SlideBloco
    extra = 0
    fields = ('ordem', 'tipo', 'widget')
    readonly_fields = ('criado_em',)


@admin.register(Deck)
class DeckAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tenant', 'criado_por', 'compartilhado', 'snapshot_em', 'atualizado_em')
    list_filter = ('compartilhado', 'tenant')
    search_fields = ('nome', 'descricao')
    inlines = [SlideInline]
    readonly_fields = ('criado_em', 'atualizado_em', 'snapshot_em')


@admin.register(Slide)
class SlideAdmin(admin.ModelAdmin):
    list_display = ('deck', 'ordem', 'titulo')
    list_filter = ('deck__tenant',)
    inlines = [SlideBlocoInline]
    readonly_fields = ('criado_em', 'atualizado_em')


@admin.register(SlideBloco)
class SlideBlocoAdmin(admin.ModelAdmin):
    list_display = ('slide', 'ordem', 'tipo', 'widget')
    list_filter = ('tipo',)
    readonly_fields = ('criado_em', 'atualizado_em')
