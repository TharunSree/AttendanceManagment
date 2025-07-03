import os
from io import BytesIO
from django.conf import settings
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa


def link_callback(uri, rel):
    """
    This crucial function converts relative HTML URIs (like /static/css/...)
    to absolute system paths so xhtml2pdf can find the necessary files.
    """
    # Handle MEDIA_URL for student photos
    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, "", 1))
    # Handle STATIC_URL for CSS files
    elif uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.STATIC_ROOT, uri.replace(settings.STATIC_URL, "", 1))
    else:
        # handle absolute paths
        if os.path.isabs(uri):
            path = uri
        else:
            # handle relative paths
            path = os.path.join(settings.STATIC_ROOT, uri)

    # Ensure the file actually exists
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Static file not found: {path}")
    return path


def render_to_pdf(template_src, context_dict={}):
    """
    Takes a Django template path and a context dictionary,
    and returns an HttpResponse object with the rendered PDF.
    """
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()

    # Create the PDF document, using our link_callback to find static files
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result, link_callback=link_callback)

    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')

    # If there's an error, return an error response
    return HttpResponse(f'We had some errors creating the PDF<pre>{html}</pre>', status=400)