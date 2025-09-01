// Test EspoCRM API calls
Espo.Ajax.getRequest('Lead/action/list');
Ajax.postRequest('Account/create', {name: 'Test'});
this.ajax.deleteRequest('Contact/123');
