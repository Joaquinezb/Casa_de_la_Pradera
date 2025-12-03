from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.shortcuts import redirect


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        if not username or not password:
            return render(request, 'login.html', {'error': 'Por favor, completa todos los campos'})
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                return redirect('dashboard')  # redirige al dashboard de core
            else:
                return render(request, 'login.html', {'error': 'Tu cuenta está desactivada. Contacta al administrador.'})
        else:
            return render(request, 'login.html', {'error': 'Usuario o contraseña incorrectos'})
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('usuarios:login')