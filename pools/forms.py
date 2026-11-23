from django import forms

from .models import PricingTier, Service


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
