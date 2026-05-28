from rest_framework.pagination import PageNumberPagination


class FlexiblePagination(PageNumberPagination):
    """Allows clients to control page size via `page_size` query param, up to 100."""
    page_size_query_param = 'page_size'
    max_page_size = 100
