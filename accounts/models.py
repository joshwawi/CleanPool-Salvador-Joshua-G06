from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)  # always hashed (BR-05)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("role", User.ROLE_ADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("full_name", "Administrator")
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CLIENT = "client"
    ROLE_PROVIDER = "provider"
    ROLE_ADMIN = "admin"
    ROLE_CHOICES = [
        (ROLE_CLIENT, "Client (Business Owner/Manager)"),
        (ROLE_PROVIDER, "Cleaning Service Provider"),
        (ROLE_ADMIN, "System Administrator"),
    ]
    STATUS_CHOICES = [("active", "Active"), ("suspended", "Suspended")]

    user_id = models.AutoField(primary_key=True)
    email = models.EmailField(max_length=120, unique=True)  # BR-01
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_CLIENT)  # BR-02
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")  # BR-04
    profile_photo = models.ImageField(upload_to="profile_photos/", blank=True, null=True)
    failed_login_count = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)  # BR-03
    created_at = models.DateTimeField(default=timezone.now)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"

    def __str__(self):
        return f"{self.full_name} <{self.email}>"

    @property
    def is_suspended(self):
        return self.status == "suspended"

    @property
    def is_locked(self):
        return bool(self.locked_until and self.locked_until > timezone.now())
