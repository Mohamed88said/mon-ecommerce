from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import View
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from returns.models import ReturnRequest, Refund
from returns.forms import ReturnReviewForm, ReturnRequestForm
from store.models import Order, Notification
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import stripe
import paypalrestsdk
from django.conf import settings
from django.http import HttpResponseBadRequest
from django.core.exceptions import ValidationError
import logging

# Configuration des clés API
stripe.api_key = settings.STRIPE_SECRET_KEY
paypalrestsdk.configure({
    "mode": settings.PAYPAL_MODE,
    "client_id": settings.PAYPAL_CLIENT_ID,
    "client_secret": settings.PAYPAL_CLIENT_SECRET
})

# Configuration du logging
logger = logging.getLogger(__name__)

class ReturnRequestCreateView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'returns/return_form.html'

    def test_func(self):
        return self.request.user.user_type == 'buyer'

    def get(self, request, *args, **kwargs):
        order = get_object_or_404(Order, id=self.kwargs['order_id'], user=self.request.user, status='delivered')
        form = ReturnRequestForm(user=self.request.user)
        return render(request, self.template_name, {'form': form, 'order': order})

    def post(self, request, *args, **kwargs):
        order = get_object_or_404(Order, id=self.kwargs['order_id'], user=self.request.user, status='delivered')
        try:
            print(f"POST data received: {request.POST}")
            form = ReturnRequestForm(
                request.POST,
                request.FILES or None,
                user=self.request.user,
                instance=ReturnRequest(order=order)
            )
            if form.is_valid():
                print("Formulaire valide, sauvegarde en cours...")
                return_request = form.save(commit=False)
                return_request.order = order
                return_request.user = request.user
                return_request.save()
                print(f"Demande de retour #{return_request.id} sauvegardée.")
                
                sellers_notified = set()
                for item in order.items.all():
                    if item.product.seller and item.product.seller not in sellers_notified:
                        print(f"Création notification pour vendeur {item.product.seller.username}")
                        notification = Notification.objects.create(
                            user=item.product.seller,
                            message=f"Une demande de retour a été soumise pour la commande #{order.id}.",
                            notification_type='return_request',
                            related_object_id=return_request.id
                        )
                        channel_layer = get_channel_layer()
                        try:
                            async_to_sync(channel_layer.group_send)(
                                f'notifications_{item.product.seller.id}',
                                {
                                    'type': 'new_notification',
                                    'message': f"Nouvelle demande de retour #{return_request.id} pour la commande #{order.id}",
                                    'notification_type': 'return_request',
                                    'timestamp': return_request.created_at.isoformat()
                                }
                            )
                            print(f"Notification WebSocket envoyée au vendeur {item.product.seller.username}")
                        except Exception as e:
                            print(f"Erreur lors de l'envoi de la notification WebSocket : {str(e)}")
                        sellers_notified.add(item.product.seller)
                messages.success(request, "Demande de retour soumise avec succès.")
                return redirect('store:order_detail', order_id=order.id)
            else:
                print(f"Form errors: {form.errors}")
                messages.error(request, f"Erreur dans le formulaire de demande de retour : {form.errors}")
                return render(request, self.template_name, {'form': form, 'order': order})
        except Exception as e:
            print(f"Erreur inattendue dans post: {str(e)}")
            messages.error(request, f"Une erreur est survenue : {str(e)}")
            return HttpResponseBadRequest("Erreur lors du traitement de la demande")

class ReturnRequestListView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'returns/return_list.html'

    def test_func(self):
        return self.request.user.user_type == 'buyer'

    def get(self, request, *args, **kwargs):
        return_requests = ReturnRequest.objects.filter(user=self.request.user).order_by('-created_at')
        return render(request, self.template_name, {'return_requests': return_requests})

class ReturnRequestReviewView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'returns/return_review.html'

    def test_func(self):
        return_request = get_object_or_404(ReturnRequest, id=self.kwargs['return_id'])
        return self.request.user.user_type == 'seller' and any(
            item.product.seller == self.request.user for item in return_request.order.items.all()
        )

    def get(self, request, *args, **kwargs):
        return_request = get_object_or_404(ReturnRequest, id=self.kwargs['return_id'])
        form = ReturnReviewForm(instance=return_request)
        return render(request, self.template_name, {'form': form, 'return_request': return_request})

    def post(self, request, *args, **kwargs):
        return_request = get_object_or_404(ReturnRequest, id=self.kwargs['return_id'])
        form = ReturnReviewForm(request.POST, instance=return_request)
        if form.is_valid():
            return_request = form.save()
            channel_layer = get_channel_layer()
            if return_request.status == 'APPROVED':
                try:
                    if not return_request.order.charge_id:
                        logger.error(f"Aucun charge_id trouvé pour la commande #{return_request.order.id}")
                        messages.error(request, f"Aucun charge_id trouvé pour la commande #{return_request.order.id}. Contactez l'administrateur.")
                        return render(request, self.template_name, {'form': form, 'return_request': return_request})

                    if return_request.order.payment_method == 'card':
                        charge_id = return_request.order.charge_id
                        logger.info(f"Tentative de remboursement pour la commande #{return_request.order.id}, charge_id={charge_id}")

                        # Vérifier que le Charge ID existe
                        try:
                            stripe.Charge.retrieve(charge_id)
                        except stripe.error.InvalidRequestError as e:
                            logger.error(f"Charge ID {charge_id} non trouvé ou invalide : {str(e)}")
                            messages.error(request, f"Charge ID {charge_id} non trouvé ou invalide. Contactez l'administrateur.")
                            return render(request, self.template_name, {'form': form, 'return_request': return_request})

                        # Vérifier si un remboursement existe déjà
                        if not Refund.objects.filter(return_request=return_request).exists():
                            refund = stripe.Refunded.create(
                                charge=charge_id,
                                amount=int(return_request.order.total * 100),  # Montant en centimes
                            )
                            transaction_id = refund.id
                            Refund.objects.create(
                                return_request=return_request,
                                amount=return_request.order.total,
                                method='card',
                                transaction_id=transaction_id,
                                status='COMPLETED'
                            )
                            return_request.status = 'COMPLETED'
                            return_request.save()
                            logger.info(f"Remboursement Stripe réussi pour la commande #{return_request.order.id}, refund_id={refund.id}")
                        else:
                            messages.warning(request, "Un remboursement existe déjà pour cette demande de retour.")
                            logger.warning(f"Remboursement déjà existant pour la demande #{return_request.id}")

                    elif return_request.order.payment_method == 'paypal':
                        paypalrestsdk.configure({
                            "mode": settings.PAYPAL_MODE,
                            "client_id": settings.PAYPAL_CLIENT_ID,
                            "client_secret": settings.PAYPAL_CLIENT_SECRET
                        })
                        charge_id = return_request.order.charge_id
                        refund = paypalrestsdk.Sale.find(charge_id).refund({
                            "amount": {"total": str(return_request.order.total), "currency": "EUR"},
                        })
                        if refund.success():
                            transaction_id = refund.id
                            Refund.objects.create(
                                return_request=return_request,
                                amount=return_request.order.total,
                                method='paypal',
                                transaction_id=transaction_id,
                                status='COMPLETED'
                            )
                            return_request.status = 'COMPLETED'
                            return_request.save()
                            logger.info(f"Remboursement PayPal réussi pour la demande #{return_request.id}, refund_id={refund.id}")
                        else:
                            logger.error(f"Échec du remboursement PayPal pour la demande #{return_request.id}: {refund.error['message']}")
                            messages.error(request, f"Erreur lors du remboursement PayPal : {refund.error['message']}")
                            return render(request, self.template_name, {'form': form, 'return_request': return_request})

                    else:
                        logger.error(f"Méthode de paiement non supportée pour la commande #{return_request.order.id}: {return_request.order.payment_method}")
                        raise ValidationError("Méthode de paiement non supportée.")

                    Notification.objects.create(
                        user=return_request.user,
                        message=f"Votre demande de retour pour la commande #{return_request.order.id} a été approuvé et remboursée.",
                        notification_type='return_approved',
                        related_object_id=return_request.id
                    )
                    async_to_sync(channel_layer.group_send)(
                        f'notifications_{return_request.user.id}',
                        {
                            'type': 'new_notification',
                            'message': f"Votre demande de retour #{return_request.id} a été approuvée et remboursée.",
                            'notification_type': 'return_approved',
                            'timestamp': return_request.updated_at.isoformat()
                        }
                    )

                except (stripe.error.StripeError, paypalrestsdk.exceptions.ResourceNotFound, ValidationError) as e:
                    logger.error(f"Erreur lors du remboursement pour la demande #{return_request.id}: {str(e)}")
                    messages.error(request, f"Erreur lors du traitement du remboursement : {str(e)}")
                    return render(request, self.template_name, {'form': form, 'return_request': return_request})

            messages.success(request, f"Demande de retour #{return_request.id} mise à jour avec succès.")
            return redirect('dashboard:orders')
        return render(request, self.template_name, {'form': form, 'return_request': return_request})