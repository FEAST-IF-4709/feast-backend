from rest_framework.pagination import CursorPagination


class OrderCursorPagination(CursorPagination):
    ordering = "-placed_at"
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100
    cursor_query_param = "cursor"
