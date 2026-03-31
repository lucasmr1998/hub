import os
from django.core.exceptions import ValidationError


ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB


def validate_image_upload(file):
    """Validate uploaded image file type and size."""
    ext = os.path.splitext(file.name)[1].lower().lstrip('.')
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f'Tipo de arquivo não permitido: .{ext}. '
            f'Tipos aceitos: {", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))}'
        )
    if file.size > MAX_IMAGE_SIZE:
        max_mb = MAX_IMAGE_SIZE / (1024 * 1024)
        raise ValidationError(
            f'Arquivo muito grande ({file.size / (1024*1024):.1f}MB). '
            f'Tamanho máximo: {max_mb:.0f}MB.'
        )


def tenant_upload_path(instance, filename):
    """Generate tenant-isolated upload path."""
    tenant_id = getattr(instance, 'tenant_id', None) or 'shared'
    model_name = instance.__class__.__name__.lower()
    return f'tenants/{tenant_id}/{model_name}/{filename}'
