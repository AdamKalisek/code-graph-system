
// Test API calls
function loadUser(userId) {
    fetch('/api/v1/User/' + userId)
        .then(res => res.json())
        .then(data => console.log(data));
    
    $.ajax({
        url: '/api/v1/Lead',
        method: 'POST',
        data: {name: 'Test'}
    });
    
    axios.get('/api/v1/Account')
        .then(response => console.log(response));
}
