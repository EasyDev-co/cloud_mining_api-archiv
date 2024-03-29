import jwt
from rest_framework import serializers, exceptions
from rest_framework.settings import api_settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.auth import get_user_model, authenticate
from django.core import exceptions as django_exceptions
from django.core.validators import RegexValidator
from django.core.validators import EmailValidator
from django.utils.encoding import force_str, DjangoUnicodeDecodeError
from django.utils.http import urlsafe_base64_decode
from django.conf import settings

from src.users.api.v1.validation_pattern import PHONE_NUMBER_PATTERN


User = get_user_model()


class UserRegisterSerializer(serializers.ModelSerializer):
    """Сериализация имени пользователя и паролей."""

    password = serializers.CharField(
        style={"input_type": "password"}, write_only=True
    )
    password_confirm = serializers.CharField(
        style={"input_type": "password"}, write_only=True
    )

    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'password_confirm']

    def validate(self, attrs):
        validated_data = super().validate(attrs)
        password: str = attrs.get("password", '')
        password_confirm: str = attrs.get("password_confirm", '')
        attrs.pop('password_confirm')
        user = self.Meta.model(**attrs)

        if password == password_confirm:
            try:

                validate_password(password, user)
            except django_exceptions.ValidationError as e:
                serializer_error = serializers.as_serializer_error(e)
                raise serializers.ValidationError(
                    {"password": serializer_error[
                        api_settings.NON_FIELD_ERRORS_KEY
                    ]
                    }
                )

            return validated_data
        raise serializers.ValidationError(
            {
                "password": 'The passwords entered do not match.',
                "password_confirm": 'The passwords entered do not match.'
            }
        )

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserTokenSerializer(serializers.Serializer):
    """
    Сериализация токена.

    После валидации в случае успеха вернет токен и uuid
    пользователя.
    """
    token = serializers.CharField(write_only=True)
    uuid = serializers.CharField(read_only=True)

    def validate(self, attrs):
        validated_data = super().validate(attrs)
        token = attrs.get('token', '')
        try:
            token_data = jwt.decode(
                token,
                settings.SECRET_KEY, algorithms=['HS256'])
            user = User.objects.get(pk=token_data.get('user_uuid'))
        except (
            User.DoesNotExist,
            ValueError,
            TypeError,
            OverflowError,
            jwt.DecodeError
        ):
            raise exceptions.NotAcceptable(
                {"link": 'An activation link is invalid.'}
            )
        except jwt.ExpiredSignatureError:
            raise exceptions.NotAcceptable(
                {'link': 'An activation link has expired.'}
            )
        validated_data['uuid'] = user.uuid
        return validated_data


class ResendActivationAccountEmailSerializer(serializers.ModelSerializer):
    """
    Сериализация адреса эл.почты при повторной активации аккаунта.
    """
    email = serializers.EmailField(validators=[EmailValidator, ])

    class Meta:
        model = User
        fields = ['email', ]

    def validate(self, attrs):
        validated_data = super().validate(attrs)
        email = attrs.get('email', '')
        try:
            user = self.Meta.model.objects.get(email=email)
        except self.Meta.model.DoesNotExist:
            raise exceptions.NotFound(
                detail={'email': 'An email does not exist.'}
            )
        if user.is_confirm:
            raise exceptions.NotFound(
                detail={'user': 'An user is already confirm.'}
            )
        return validated_data


class LoginUserSerializer(serializers.ModelSerializer):
    """
    Сериализация юзернейма и пароля.

    В случае успеха вернет access и refresh токены.
    """
    password = serializers.CharField(
        style={"input_type": "password"}, write_only=True
    )
    username = serializers.CharField(write_only=True)
    tokens = serializers.DictField(read_only=True)

    class Meta:
        model = User
        fields = ['username', 'password', 'tokens']

    def validate(self, attrs):
        validated_data = super().validate(attrs)
        username = attrs.get('username', '')
        password = attrs.get('password', '')
        user = authenticate(username=username, password=password)
        if not user:
            raise exceptions.ValidationError(
                detail={
                    "new_password": 'Invalid credential.'
                }
            )
        if not user.is_confirm:
            raise exceptions.ValidationError(
                detail={'account': 'An account is not confirm.'}
            )
        validated_data['tokens'] = user.tokens
        return validated_data


class SendResetPasswordEmailSerializer(serializers.ModelSerializer):
    """
    Сериализация адреса эл.почты при сбросе пароля.
    """
    email = serializers.EmailField(validators=[EmailValidator, ])

    class Meta:
        model = User
        fields = ['email', ]

    def validate(self, attrs):
        validated_data = super().validate(attrs)
        email = attrs.get('email', '')
        try:
            self.Meta.model.objects.get(email=email)
        except self.Meta.model.DoesNotExist:
            raise exceptions.NotFound(
                detail={'email': 'An email does not exist.'}
            )
        return validated_data


class CheckNewPasswordSerializer(serializers.ModelSerializer):
    """
    Сериализация паролей при сбросе старого пароля
    """
    password = serializers.CharField(
        style={"input_type": "password"}
    )
    password_confirm = serializers.CharField(
        style={"input_type": "password"}, write_only=True
    )

    class Meta:
        model = User
        fields = ['password', 'password_confirm']

    def validate(self, attrs):
        password: str = attrs.get("password", '')
        password_confirm: str = attrs.get("password_confirm", '')
        if password == password_confirm:
            try:
                validate_password(password, self.Meta.model)
            except django_exceptions.ValidationError as e:
                serializer_error = serializers.as_serializer_error(e)
                raise serializers.ValidationError(
                    {"password": serializer_error[
                        api_settings.NON_FIELD_ERRORS_KEY
                    ]
                    }
                )
            validated_data = super().validate(attrs)
            return validated_data
        raise serializers.ValidationError(
            {
                "password": 'The passwords entered do not match.',
                "password_confirm": 'The passwords entered do not match.'
            }
        )

    def update(self, instance, validated_data):
        instance.set_password(validated_data.get('password'))
        instance.save()
        return instance


class ChangeUserFirstNameSerializer(serializers.ModelSerializer):
    """
    Сериализация имени пользователя при ее изменении
    """
    first_name = serializers.CharField()

    class Meta:
        model = User
        fields = ['first_name', ]

    def update(self, instance, validated_data):
        instance.first_name = (validated_data.get('first_name'))
        instance.save()
        return instance


class ChangeUserLastNameSerializer(serializers.ModelSerializer):
    """
    Сериализация фамилии пользователя при ее изменении
    """
    last_name = serializers.CharField()

    class Meta:
        model = User
        fields = ['last_name', ]

    def update(self, instance, validated_data):
        instance.last_name = (validated_data.get('last_name'))
        instance.save()
        return instance


class ChangeUserPhoneNumberSerializer(serializers.ModelSerializer):
    """
    Сериализация номера телефона пользователя при его изменении
    """
    phone_number = serializers.CharField(validators=[RegexValidator(
        regex=PHONE_NUMBER_PATTERN,
        message='Incorrect phone number. The number must consist of digits and\
 the first digit cannot be zero.'
    ), ],
        min_length=8,
        max_length=15,
    )

    class Meta:
        model = User
        fields = ['phone_number', ]

    def validate(self, attrs):
        phone_number = attrs.get('phone_number')
        if self.Meta.model.objects.filter(phone_number=phone_number).exists():
            raise exceptions.ValidationError(
                detail={
                    'phone_number': 'A current phone number already exists.'
                }
            )
        validated_data = super().validate(attrs)
        return validated_data

    def update(self, instance, validated_data):
        instance.phone_number = (validated_data.get('phone_number'))
        instance.save()
        return instance


class ChangeUserPasswordSerializer(serializers.ModelSerializer):
    """
    Сериализация нового пароля пользователя при его изменении
    """
    current_password = serializers.CharField(
        style={"input_type": "password"}, write_only=True
    )
    new_password = serializers.CharField(
        style={"input_type": "password"}, write_only=True
    )
    new_password_confirm = serializers.CharField(
        style={"input_type": "password"}, write_only=True
    )

    class Meta:
        model = User
        fields = ['current_password', 'new_password', 'new_password_confirm']

    def validate(self, attrs):
        new_password: str = attrs.get("new_password", '')
        new_password_confirm: str = attrs.get("new_password_confirm", '')
        if new_password == new_password_confirm:
            try:
                validate_password(new_password, self.Meta.model)
            except django_exceptions.ValidationError as e:
                serializer_error = serializers.as_serializer_error(e)
                raise serializers.ValidationError(
                    {"new_password": serializer_error[
                        api_settings.NON_FIELD_ERRORS_KEY
                    ]
                    }
                )
            validated_data = super().validate(attrs)
            return validated_data
        raise serializers.ValidationError(
            {
                "new_password": 'The passwords entered do not match.',
                "new_password_confirm": 'The passwords entered do not match.'
            }
        )

    def update(self, instance, validated_data):
        if not instance.check_password(validated_data.get('current_password')):
            raise serializers.ValidationError(
                {"current_password": "Current password is not correct."})
        instance.set_password(validated_data.get('new_password'))
        instance.save()
        return instance


class ChangeUserEmailSerializer(serializers.ModelSerializer):
    """
    Сериализация эл.почты пользователя при ее изменении
    """
    email = serializers.EmailField(validators=[EmailValidator, ])

    class Meta:
        model = User
        fields = ['email', ]

    def validate(self, attrs):
        validated_data = super().validate(attrs)
        email = attrs.get('email', '')
        if self.Meta.model.objects.filter(email=email).exists():
            raise exceptions.ValidationError(
                detail={'email': 'An email is already exist.'}
            )
        return validated_data


class UserTokenUIDSerializer(serializers.ModelSerializer):
    """
    Сериализация токена и uidb64
    """
    token = serializers.CharField(write_only=True)
    uidb64 = serializers.CharField(write_only=True)
    uuid = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ['token', 'uidb64', 'uuid']

    def validate(self, attrs):
        uidb64 = attrs.get('uidb64', '')
        token = attrs.get('token', '')
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = self.Meta.model.objects.get(pk=uid)
        except (
            TypeError,
            ValueError,
            OverflowError,
            User.DoesNotExist,
            DjangoUnicodeDecodeError
        ):
            raise exceptions.NotAuthenticated(
                detail={'uuid': 'An uuid is not valid.'},
            )
        if not PasswordResetTokenGenerator().check_token(user, token):
            raise exceptions.NotAuthenticated(
                detail={'token': 'A token is not valid.'}
            )
        return {
            'uuid': uid
        }


class ChangeUserUsernameSerializer(serializers.ModelSerializer):
    """
    Сериализация юзернейма для его изменения
    """
    username = serializers.CharField()

    class Meta:
        model = User
        fields = ['username', ]

    def validate_username(self, value):
        username = value
        if self.Meta.model.objects.filter(username=username).exists():
            raise exceptions.ValidationError(
                detail='An username is already exist.'
            )
        return value

    def update(self, instance, validated_data):
        instance.username = (validated_data.get('username'))
        instance.save()
        return instance
