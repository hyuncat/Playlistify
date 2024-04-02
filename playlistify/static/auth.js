// Script used to delay redirecting the user to the Spotify login page
document.querySelector('form').addEventListener('submit', function(event) {
    event.preventDefault();

    fetch('/auth')
        .then(response => response.json())
        .then(data => setTimeout(() => window.location.href = data.redirect, 1000));
});