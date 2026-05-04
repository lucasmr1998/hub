# Hubtrix — Site comercial (mockup HTML)

Conversão estática da Home do Paper.design para HTML.

## Como visualizar

Basta abrir `index.html` direto no navegador (duplo clique ou arrastar). Não precisa de build, servidor ou npm. As fontes vêm do Google Fonts e o CSS via Tailwind Play CDN.

```
# Opcional: servidor local pra simular ambiente real
python -m http.server 8080 --directory site
# depois: http://localhost:8080
```

## O que tem aqui

- `index.html` — Home completa (1440px de largura, layout idêntico ao do Paper)
- Sem mobile ainda (Paper só tem desktop). Adicionar quando o Paper resetar.

## Stack

- HTML estático
- Tailwind v3 via [Play CDN](https://tailwindcss.com/docs/installation/play-cdn) com config inline
- Google Fonts: Inter, Inter Tight, Caveat (para a marginalia)

## Próximos passos (decididos)

1. **Decidir stack final** — Next.js + Tailwind + Vercel é a proposta, falta confirmar
2. **Migrar pra projeto buildado** quando for pra produção (Tailwind Play CDN não é pra prod)
3. **Páginas Produto e Demo** — designs prontos no Paper, falta converter
4. **Versão mobile** — falta no Paper, fazer quando resetar limite
5. **Substituir placeholders** (números, depoimento, screenshot) por dados reais com autorização

## Princípios da marca aplicados

Detalhes em [robo/docs/BRAND/](../robo/docs/BRAND/):
- Cobalto `#1D4ED8` = ação. Não decoração
- Burnt sienna `#E76F51` = marginalia (sublinhado SVG sob "fideliza sempre" no hero)
- Tinta `#0B1220` = texto e backgrounds escuros
- Inter Tight (display) + Inter (corpo)
- Editorial, anti cara-de-IA
