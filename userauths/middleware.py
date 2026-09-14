from django.shortcuts import redirect


class AdminPortalIsolationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if (
            user.is_authenticated
            and user.is_staff
            and user.is_approved_admin
            and not request.path.startswith("/admin/")
            and request.path not in {"/user/sign-out/", "/user/admin-login/"}
        ):
            return redirect("/admin/")
        return self.get_response(request)
