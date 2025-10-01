from rest_framework.pagination import PageNumberPagination

class ReelPagination(PageNumberPagination):
    page_size = 10

    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)

        # seed'ni qo‘shib yuboramiz
        seed = self.request.query_params.get("seed")
        if seed:
            if response.data["next"]:
                response.data["next"] += f"&seed={seed}"
            if response.data["previous"]:
                response.data["previous"] += f"&seed={seed}"

        return response

class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50

class CommentPagination(PageNumberPagination):
    page_size = 10  # har bir sahifada nechta comment chiqsin
    page_size_query_param = "page_size"  # ?page_size=20 bilan dinamik o‘zgartirish mumkin
    max_page_size = 50


class MoviePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50

class CoursePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50

class ChannelPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50