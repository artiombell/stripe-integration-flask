
import os
import stripe


from flask import Flask, json, jsonify, redirect, request
from werkzeug.utils import send_from_directory
from werkzeug.wrappers.response import Response

app = Flask(__name__,
            static_url_path='', 
            static_folder='web/static',
            template_folder='web/templates')

stripe.api_key =  'sk_test_<>'
endpoint_secret = 'whsec_<>'
stripe_customer = 'cus_<>'
smart_trash_bag = 'prod_<>'
smart_bin = 'prod_<>'

@app.route('/create-checkout-session', methods=['GET'])
def create_checkout_session(customer_data = None, list_items = None):
    """
    This method is routed to during the purchase session. 
    """
    # could be retrieved from the session object or registration
    #  page of the web store if customer is logged in or begins registration
    customer_data = None 

    # data form web store shopping-cart (could be retrieved from DB)
    list_items=[
        {
            'price': smart_bin,
            'quantity': 1
        }
    ]



    # filled out based on info if customer is authenticated on the web site and already has payment information registered in the DB. 
    session = stripe.checkout.Session.create(
        payment_intent_data={
            'setup_future_usage': 'off_session', 
        },
        payment_method_types=['card'],
        line_items=list_items,
        mode='payment',
        success_url='http://localhost:4242/success.html',
        cancel_url='http://localhost:4242/cancel.html',

    )

    return redirect(session.url, code=303)

@app.route('/<path:path>')
def static_file(path):
    return app.send_static_file(path)


@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Captures events from Stripe Session
    """
    event = None
    payload = request.data
    sig_header = request.headers['STRIPE_SIGNATURE']

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        raise e
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise e

    # Handle the event
    if event['type'] == 'payment_method.attached':
        payment_method = event['data']['object']
        customer = stripe_customer # get customer from DB
        if customer.is_newcustomer:
            payment_method = event['data']['object']

        # sets the customer default payment mehtod
        customer = stripe.Customer.modify(
            customer, # customer id
            invoice_settings={'default_payment_method': payment_method['id']},
        )
    
    elif event['type'] == 'customer.created':
        customer = event['data']['object']
       
        # save customer to db here [MARK AS NEW CUSTOMER]
        # db op here

        pass
    
    else:
      print('Unhandled event type {}'.format(event['type']))

    # 

    return jsonify(success=True)


@app.route('/list-invoices', methods=['GET'])
def get_invoices(customer = None):
    invoices = stripe.Invoice.list(
        customer = stripe_customer
    )

    return jsonify(invoices)


@app.route('/invoice/<invoice_id>', methods=['GET'])
def get_invoice(invoice_id):
    invoice = stripe.Invoice.retrieve(
        invoice_id,
    )
    return jsonify(invoice)

@app.route('/list-payment-methods', methods=['GET'])
def list_payment_methods(customer_id = None):
    customer_id = stripe_customer
    payment_methods = stripe.PaymentMethod.list(
        customer=customer_id,
        type="card",
    )

    return jsonify(payment_methods)

@app.route('/<payment_method_id>', methods=['DELETE'])
def delete_payment_method(payment_method_id):
    stripe.PaymentMethod.detach(
        payment_method_id,
    )

@app.route('/add-payment-method', methods=['GET'])
def add_payment_method(stripe_payment_method_id):
    """
    UI will collect payment infomration and send it to Stripe. In return it will get a token pm_*****
    """
    payment_method = stripe.PaymentMethod.attach(
        stripe_payment_method_id,
        customer=stripe_customer,
    )
    
    # store id in DB. 

    return jsonify(payment_method)

@app.route('/renew-purchase', methods=['GET'])
def renew_purchase(session = None, items=[]):
    """
    Connects to the and sets the state of the items 
    """
    
    customer = '' # 'Customer info retrieved from DB.'



    price = stripe.Price.create(
        product=smart_trash_bag,
        unit_amount=1099,
        currency='usd',
    )

    stripe.InvoiceItem.create(
        customer=stripe_customer,
        price=price['id'],
    )

    invoice = stripe.Invoice.create(
        customer=stripe_customer,
        auto_advance=True # auto-finalize this draft after ~1 hour
    )

    #if customer has Auto-Collect turned on, then collect (perhaps auto-collect PLUS stripe feature?)
    invoice = stripe.Invoice.finalize_invoice(invoice['id'])
    invoice = stripe.Invoice.pay(invoice)

    return jsonify(invoice)


if __name__== '__main__':
    app.run(port=4242)