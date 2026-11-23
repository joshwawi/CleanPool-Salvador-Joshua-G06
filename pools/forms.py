from datetime import date
from decimal import Decimal

from django import forms

from .models import Pool, PoolMembership, PricingTier, Service


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["title", "category", "service_area", "price_per_sqm", "description", "is_published"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 5:
            raise forms.ValidationError("Title must be at least 5 characters.")
        return title


class PricingTierForm(forms.ModelForm):
    class Meta:
        model = PricingTier
        fields = ["min_participants", "discount_percent"]

    def __init__(self, *args, service=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = service

    def clean_min_participants(self):
        n = self.cleaned_data["min_participants"]
        if self.service and self.service.tiers.filter(min_participants=n).exists():
            raise forms.ValidationError("A tier for this number of businesses already exists.")
        return n


class PoolForm(forms.ModelForm):
    # Only used when creating: the creator's own share is saved as the first membership.
    business_name = forms.CharField(max_length=120, label="Your business name", required=False)
    area_sqm = forms.DecimalField(min_value=Decimal("10"), max_digits=8, decimal_places=2, required=False,
                                  label="Your area to clean (sqm)")

    class Meta:
        model = Pool
        fields = ["service", "title", "location", "scheduled_date", "max_participants", "notes"]
        widgets = {"scheduled_date": forms.DateInput(attrs={"type": "date"}), "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.creating = self.instance.pk is None
        self.fields["service"].queryset = Service.objects.filter(is_published=True)
        self.fields["service"].label_from_instance = lambda s: f"{s.title} – {s.service_area} (₱{s.price_per_sqm}/sqm)"
        if self.creating:
            self.fields["business_name"].required = True
            self.fields["area_sqm"].required = True
        else:
            del self.fields["business_name"], self.fields["area_sqm"]
            self.fields["service"].disabled = True  # cannot switch provider after members joined
            self.fields["service"].queryset = Service.objects.filter(pk=self.instance.service_id)

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 5:
            raise forms.ValidationError("Title must be at least 5 characters.")
        return title

    def clean_scheduled_date(self):
        d = self.cleaned_data["scheduled_date"]
        if d <= date.today():
            raise forms.ValidationError("Choose a date in the future.")
        return d

    def clean_max_participants(self):
        n = self.cleaned_data["max_participants"]
        if not self.creating and n < self.instance.participant_count:
            raise forms.ValidationError(f"{self.instance.participant_count} businesses already joined; cannot go below that.")
        return n


class MembershipForm(forms.ModelForm):
    class Meta:
        model = PoolMembership
        fields = ["business_name", "area_sqm", "notes"]
