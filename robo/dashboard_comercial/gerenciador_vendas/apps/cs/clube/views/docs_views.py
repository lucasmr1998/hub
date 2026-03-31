from django.shortcuts import render
from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
import os
import markdown


@login_required
@user_passes_test(lambda u: u.is_staff)
def documentacao(request):
    """
    Renderiza o arquivo DOCUMENTACAO.md dentro do layout do dashboard.
    """
    md_path = os.path.join(settings.BASE_DIR, 'DOCUMENTACAO.md')
    if not os.path.exists(md_path):
        return render(request, 'clube/dashboard/documentacao.html', {'html_content': '<p>Arquivo de documentacao nao encontrado.</p>'})

    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    html_content = markdown.markdown(
        md_content,
        extensions=['tables', 'toc', 'fenced_code', 'nl2br']
    )

    return render(request, 'clube/dashboard/documentacao.html', {'html_content': html_content})
