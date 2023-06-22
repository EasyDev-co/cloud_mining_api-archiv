from faker import Faker
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.urls import reverse
from rest_framework.response import Response
from src.tests import CreateUsersTestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from src.users.api.v1.views import (
    UserRegistrationView,
    ResendActivationAccountEmailView,
    ResetPasswordView,
    ChangeUserEmailView
)
from src.users.models import NewEmail

User = get_user_model()


fake = Faker()


def post_for_activation_account_email_fake(self, request):
    user = request.data
    serializer = self.serializer_class(data=user)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    user_data = serializer.data
    user = User.objects.get(email=user_data.get('email'))
    token = RefreshToken.for_user(user).access_token
    user_data['token'] = str(token)
    return Response(user_data, status=status.HTTP_201_CREATED)


def get_for_activation_account_email_fake(self, request, email):
    serializer = self.serializer_class(data={'email': email})
    serializer.is_valid(raise_exception=True)
    user_data = serializer.data
    user = User.objects.get(email=serializer.data.get('email'))
    token = RefreshToken.for_user(user).access_token
    user_data['token'] = str(token)
    return Response(data=user_data, status=status.HTTP_201_CREATED)


def post_for_reset_password_email_fake(self, request):
    serializer = self.serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = User.objects.get(email=serializer.data.get('email'))
    uidb64 = urlsafe_base64_encode(force_bytes(user.uuid))
    token = PasswordResetTokenGenerator().make_token(user)
    data = {
        'uidb64': uidb64,
        'token': token
    }
    return Response(data=data, status=status.HTTP_201_CREATED)


def post_for_change_user_email_fake(self, request):
    serializer = self.serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    NewEmail.objects.create(
        user_uuid_id=request.user.uuid, email=serializer.data.get('email')
    )
    user = request.user
    uidb64 = urlsafe_base64_encode(force_bytes(user.uuid))
    token = PasswordResetTokenGenerator().make_token(user)
    data = {
        'uidb64': uidb64,
        'token': token
    }
    return Response(data=data, status=status.HTTP_201_CREATED)


class UserTestCase(CreateUsersTestCase):

    def test_create_user_and_activate_acc(self):
        """
        — Создание аккаунта
        — Активация аккаунта
        """

        # Monkey patching
        UserRegistrationView.post = post_for_activation_account_email_fake
        profile = fake.simple_profile()
        password = fake.password()
        username = profile.get('username')
        email = fake.email()
        new_user = {
            'username': username,
            'email': email,
            'password': password,
            'password_confirm': password
        }
        # Создаем пользователя
        response = self.client.post(
            path=reverse('register'),
            data=new_user
        )
        self.assertIn('data', response.json().keys())
        new_user = response.json().get('data')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(new_user.get('username'), username)
        self.assertEqual(new_user.get('email'), email)

        # Активируем аккаунт пользователя
        response = self.client.get(
            path=reverse('activation', kwargs={'token': new_user.get('token')})
        )
        self.assertEqual(response.status_code, 204)

    def test_resend_activation_email(self):
        """
        — Создание пользователя
        — Повторное создание токена для активации акаунта
        — Активация аккаунта
        """

        # Monkey patching
        UserRegistrationView.post = post_for_activation_account_email_fake
        ResendActivationAccountEmailView.get = get_for_activation_account_email_fake
        profile = fake.simple_profile()
        password = fake.password()
        username = profile.get('username')
        email = fake.email()
        new_user = {
            'username': username,
            'email': email,
            'password': password,
            'password_confirm': password
        }
        # Создаем пользователя
        response = self.client.post(
            path=reverse('register'),
            data=new_user
        )
        self.assertIn('data', response.json().keys())
        new_user = response.json().get('data')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(new_user.get('username'), username)
        self.assertEqual(new_user.get('email'), email)
        # Отправляем повторно email для активации
        response = self.client.get(
            path=reverse('resend_activation', kwargs={'email': email})
        )
        self.assertIn('data', response.json().keys())
        resend_data = response.json().get('data')
        self.assertNotEqual(new_user.get('token'), resend_data.get('token'))
        self.assertEqual(response.status_code, 201)
        # Активируем аккаунт пользователя
        response = self.client.get(
            path=reverse('activation', kwargs={
                         'token': resend_data.get('token')})
        )
        self.assertEqual(response.status_code, 204)

    def test_create_user_non_equal_passwords(self):
        """Создание аккаунта с разными паролями"""
        UserRegistrationView.post = post_for_activation_account_email_fake
        ResendActivationAccountEmailView.get = get_for_activation_account_email_fake
        profile = fake.simple_profile()
        password_1 = fake.password()
        password_2 = fake.password()
        username = profile.get('username')
        email = fake.email()
        new_user = {
            'username': username,
            'email': email,
            'password': password_1,
            'password_confirm': password_2
        }
        # Пытаюсь создать пользователя
        response = self.client.post(
            path=reverse('register'),
            data=new_user
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('errors', response.json().keys())
        errors = response.json().get('errors')
        self.assertEqual(errors.get('password')[
                         0], 'The passwords entered do not match.')
        self.assertEqual(errors.get('password_confirm')[
                         0], 'The passwords entered do not match.')

    def test_create_user_with_exists_username(self):
        """Создание аккаунта c уже существующим username"""
        users = self.users
        user_1 = users.get('user_1')
        UserRegistrationView.post = post_for_activation_account_email_fake
        ResendActivationAccountEmailView.get = get_for_activation_account_email_fake
        password_1 = fake.password()
        password_2 = fake.password()
        username = user_1.get('username')
        email = fake.email()
        new_user = {
            'username': username,
            'email': email,
            'password': password_1,
            'password_confirm': password_2
        }
        # Пытаюсь создать пользователя
        response = self.client.post(
            path=reverse('register'),
            data=new_user
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('errors', response.json().keys())
        errors = response.json().get('errors')
        self.assertEqual(errors.get('username')[
                         0], 'A user with that username already exists.')

    def test_create_user_with_invalid_passwords(self):
        """Создание аккаунта c невалидными паролями"""
        UserRegistrationView.post = post_for_activation_account_email_fake
        ResendActivationAccountEmailView.get = get_for_activation_account_email_fake
        profile = fake.simple_profile()
        username = profile.get('username')
        email = fake.email()
        new_user = {
            'username': username,
            'email': email,
            'password': '12345678',
            'password_confirm': '12345678'
        }
        # Пытаюсь создать пользователя
        response = self.client.post(
            path=reverse('register'),
            data=new_user
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('errors', response.json().keys())
        errors = response.json().get('errors')
        self.assertEqual(errors.get('password')[
                         0], 'This password is too common.')
        self.assertEqual(errors.get('password')[
                         1], 'This password is entirely numeric.')

    def test_create_user_with_exists_email(self):
        """Создание аккаунта c уже существующим email"""
        profile = fake.simple_profile()
        users = self.users
        user_1 = users.get('user_1')
        UserRegistrationView.post = post_for_activation_account_email_fake
        ResendActivationAccountEmailView.get = get_for_activation_account_email_fake
        password_1 = fake.password()
        password_2 = fake.password()
        username = profile.get('username')
        email = user_1.get('email')
        new_user = {
            'username': username,
            'email': email,
            'password': password_1,
            'password_confirm': password_2
        }
        # Пытаюсь создать пользователя
        response = self.client.post(
            path=reverse('register'),
            data=new_user
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('errors', response.json().keys())
        errors = response.json().get('errors')
        self.assertEqual(errors.get('email')[
                         0], 'A user with that email already exists.')

    def test_create_token(self):
        """Testing token generation"""

        self.create_token()

    def test_reset_password(self):
        """Test resetting the password and creating a new password"""

        # Monkey patching
        ResetPasswordView.post = post_for_reset_password_email_fake
        ResetPasswordView.throttle_classes = []
        email = self.users.get('user_1').get('email')
        username = self.users.get('user_1').get('username')
        new_password = fake.password()
        user_data = {
            'email': email
        }
        response = self.client.post(
            path=reverse('send_email_for_reset'),
            data=user_data
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn('data', response.json().keys())
        reset_data = response.json().get('data')
        uidb64 = reset_data.get('uidb64')
        token = reset_data.get('token')
        new_password_data = {
            'password': new_password,
            'password_confirm': new_password
        }
        response = self.client.put(
            path=reverse('confirm_for_reset_password', kwargs={
                'uidb64': uidb64,
                'token': token
            }),
            content_type='application/json',
            data=new_password_data
        )
        self.assertEqual(response.status_code, 204)
        user_data = {
            'username': username,
            'password': new_password
        }
        response = self.client.post(
            path=reverse('login'),
            data=user_data
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.json().keys())
        self.assertIn('tokens', response.json().get('data').keys())
        tokens = response.json().get('data').get('tokens')
        self.assertEqual(['refresh', 'access'], list(tokens.keys()))

    def test_change_user_first_name(self):
        """Редактирование имени авторизованного пользователя"""
        self.create_token()
        users = self.users
        for _, user in users.items():
            profile = fake.simple_profile()
            full_name = profile.get('name').split(' ')
            first_name = full_name[0]
            token = user.get('token')
            auth_data = {
                'Authorization': f'Bearer {token}'
            }
            change_data = {
                'first_name': first_name
            }

            response = self.client.put(
                path=reverse('change_first_name'),
                content_type='application/json',
                headers=auth_data,
                data=change_data
            )
            self.assertEqual(response.status_code, 204)
            response = self.client.get(
                path=reverse('user'),
                headers=auth_data
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn('data', response.json().keys())
            user_data = response.json().get('data')
            self.assertEqual(user_data.get('first_name'), first_name)

    def test_change_user_last_name(self):
        """Редактирование фамилии авторизованного пользователя"""
        self.create_token()
        users = self.users
        for _, user in users.items():
            profile = fake.simple_profile()
            full_name = profile.get('name').split(' ')
            last_name = full_name[1]
            token = user.get('token')
            auth_data = {
                'Authorization': f'Bearer {token}'
            }
            change_data = {
                'last_name': last_name
            }

            response = self.client.put(
                path=reverse('change_last_name'),
                content_type='application/json',
                headers=auth_data,
                data=change_data
            )
            self.assertEqual(response.status_code, 204)
            response = self.client.get(
                path=reverse('user'),
                headers=auth_data
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn('data', response.json().keys())
            user_data = response.json().get('data')
            self.assertEqual(user_data.get('last_name'), last_name)

    def test_change_user_phone_number(self):
        """Редактирование номера телефона авторизованного пользователя"""

        self.create_token()
        users = self.users
        for _, user in users.items():
            phone_number = fake.msisdn()
            token = user.get('token')
            auth_data = {
                'Authorization': f'Bearer {token}'
            }
            change_data = {
                'phone_number': phone_number
            }

            response = self.client.put(
                path=reverse('change_phone_number'),
                content_type='application/json',
                headers=auth_data,
                data=change_data
            )
            self.assertEqual(response.status_code, 204)
            response = self.client.get(
                path=reverse('user'),
                headers=auth_data
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn('data', response.json().keys())
            user_data = response.json().get('data')
            self.assertEqual(user_data.get('phone_number'), phone_number)

    def test_change_user_phone_number_with_exist_phone_number(self):
        """Редактирование номера телефона авторизованного пользователя
        с уже существующим номером
        """

        self.create_token()
        users = self.users
        user_1 = users.get('user_1')
        exist_phone_number = user_1.get('phone_number')
        user_2 = users.get('user_2')

        token = user_2.get('token')
        auth_data = {
            'Authorization': f'Bearer {token}'
        }
        change_data = {
            'phone_number': exist_phone_number
        }
        response = self.client.put(
            path=reverse('change_phone_number'),
            content_type='application/json',
            headers=auth_data,
            data=change_data
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('errors', response.json().keys())
        errors = response.json().get('errors')
        self.assertEqual(errors.get('phone_number')[
                         0], 'An current phone number already exists.')

    def test_change_user_phone_number_with_invalid_phone_number(self):
        """Редактирование номера телефона авторизованного пользователя
        на невалидный номер
        """

        self.create_token()
        users = self.users
        user = users.get('user_1')

        token = user.get('token')
        auth_data = {
            'Authorization': f'Bearer {token}'
        }
        change_data = {
            'phone_number': '0102'
        }
        response = self.client.put(
            path=reverse('change_phone_number'),
            content_type='application/json',
            headers=auth_data,
            data=change_data
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('errors', response.json().keys())
        errors = response.json().get('errors')
        self.assertEqual(errors.get('phone_number')[
                         0], 'Incorrect phone number. The number must consist of digits.')
        self.assertEqual(errors.get('phone_number')[
                         1], 'Ensure this field has at least 8 characters.')

    def test_change_user_username(self):
        """Редактирование юзернейма авторизированного пользователя"""

        self.create_token()
        users = self.users
        for _, user in users.items():
            profile = fake.simple_profile()
            username = profile.get('username')
            token = user.get('token')
            auth_data = {
                'Authorization': f'Bearer {token}'
            }
            change_data = {
                'username': username
            }

            response = self.client.put(
                path=reverse('change_username'),
                content_type='application/json',
                headers=auth_data,
                data=change_data
            )
            self.assertEqual(response.status_code, 204)
            response = self.client.get(
                path=reverse('user'),
                headers=auth_data
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn('data', response.json().keys())
            user_data = response.json().get('data')
            self.assertEqual(user_data.get('username'), username)

    def test_change_user_username_with_exists_username(self):
        """Редактирование юзернейма авторизированного пользователя
        на уже существующей юзернейм
        """

        self.create_token()
        users = self.users
        user_1 = users.get('user_1')
        exist_username = user_1.get('username')
        user_2 = users.get('user_2')

        token = user_2.get('token')
        auth_data = {
            'Authorization': f'Bearer {token}'
        }
        change_data = {
            'username': exist_username
        }
        response = self.client.put(
            path=reverse('change_username'),
            content_type='application/json',
            headers=auth_data,
            data=change_data
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('errors', response.json().keys())
        errors = response.json().get('errors')
        self.assertEqual(errors.get('username')[
                         0], 'A user with that username already exists.')

    def test_change_user_email(self):
        """Редактирование эл. почты авторизированного пользователя
        """

        # Monkey patching
        ChangeUserEmailView.post = post_for_change_user_email_fake
        self.create_token()
        token = self.users.get('user_1').get('token')
        new_email = fake.email()
        user_data = {
            'email': new_email
        }
        auth_data = {
            'Authorization': f'Bearer {token}'
        }
        response = self.client.post(
            path=reverse('change_email'),
            data=user_data,
            headers=auth_data
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn('data', response.json().keys())
        data_for_update = response.json().get('data')
        uidb64 = data_for_update.get('uidb64')
        token = data_for_update.get('token')
        response = self.client.put(
            path=reverse('confirm_for_change_email', kwargs={
                'uidb64': uidb64,
                'token': token
            }),
            content_type='application/json',
            headers=auth_data
        )
        self.assertEqual(response.status_code, 204)
        response = self.client.get(
            path=reverse('user'),
            headers=auth_data
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.json().keys())
        user_data = response.json().get('data')
        self.assertEqual(user_data.get('email'), new_email)

    def test_change_user_email_without_link(self):
        """Редактирование эл. почты авторизированного пользователя
        без перехода по ссылке
        """

        # Monkey patching
        ChangeUserEmailView.post = post_for_change_user_email_fake
        self.create_token()
        token = self.users.get('user_1').get('token')
        old_email = self.users.get('user_1').get('email')
        new_email = fake.email()
        user_data = {
            'email': new_email
        }
        auth_data = {
            'Authorization': f'Bearer {token}'
        }
        response = self.client.post(
            path=reverse('change_email'),
            data=user_data,
            headers=auth_data
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn('data', response.json().keys())
        data_for_update = response.json().get('data')
        self.assertIn('uidb64', data_for_update.keys())
        self.assertIn('token', data_for_update.keys())
        response = self.client.get(
            path=reverse('user'),
            headers=auth_data
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.json().keys())
        user_data = response.json().get('data')
        self.assertEqual(user_data.get('email'), old_email)
        self.assertNotEqual(user_data.get('email'), new_email)

# еще можно проверять токены и uid
