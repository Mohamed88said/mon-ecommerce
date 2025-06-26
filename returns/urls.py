from django.urls import path
from . import views

app_name = 'returns'

urlpatterns = [
    path('create/<int:order_id>/', views.ReturnRequestCreateView.as_view(), name='return_create'),
    path('list/', views.ReturnRequestListView.as_view(), name='return_list'),
    path('review/<int:return_id>/', views.ReturnRequestReviewView.as_view(), name='return_review'),
]