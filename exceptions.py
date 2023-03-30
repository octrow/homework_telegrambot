class Not200Response(Exception):
    """Объявление нового класса для исключений в get_api_answer."""

    pass


class EmptyAnswerAPI(Exception):
    """Объявление нового класса для исключений в check_response."""

    pass