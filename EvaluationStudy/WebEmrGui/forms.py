from django import forms

OMISSION_CHOICES = ['I did not see it on screen',
                    'I saw it, but did not spend time considering it',
                    'I considered it in my analysis, but ultimately decided it was not relevant']

class ErrorDeterminantsForm(forms.Form):
    omission_error = forms.MultipleChoiceField(
        required=True,
        widget=forms.CheckboxSelectMultiple,
        choices=OMISSION_CHOICES,
    )
    commission_error = forms.CharField(
            required=True,
        )
