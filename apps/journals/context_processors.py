def user_journals(request):
    if not request.user.is_authenticated:
        return {"user_journals": []}
    return {
        "user_journals": [
            m.journal
            for m in request.user.memberships.select_related("journal").all()
        ]
    }
