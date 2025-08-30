/**
 * Test JavaScript API calls to EspoCRM backend
 */

define('test:api-calls', ['views/base'], function (View) {
    
    return View.extend({
        
        testSimpleApiCalls: function() {
            // Basic GET request
            this.getModelFactory().create('User').then(model => {
                model.id = userId;
                model.fetch();
            });
            
            // Ajax requests
            Espo.Ajax.getRequest('User/' + id).then(response => {
                console.log(response);
            });
            
            Espo.Ajax.postRequest('Lead', data).then(response => {
                this.model.set('id', response.id);
            });
            
            Espo.Ajax.deleteRequest('Contact/' + id);
            
            Espo.Ajax.putRequest('Account/' + id, {
                name: 'New Name',
                type: 'Customer'
            });
        },
        
        testCollectionFetch: function() {
            // Collection operations
            this.getCollectionFactory().create('Email', collection => {
                collection.where = {
                    status: 'Sent'
                };
                collection.maxSize = 50;
                collection.fetch().then(() => {
                    this.render();
                });
            });
            
            // Pagination
            this.collection.fetch({
                offset: this.offset,
                maxSize: this.maxSize,
                where: this.searchParams
            });
        },
        
        testModelOperations: function() {
            // Model save
            this.model.save({
                name: 'Test',
                status: 'New'
            }, {
                success: function() {
                    this.notify('Saved', 'success');
                }.bind(this)
            });
            
            // Model destroy
            this.model.destroy({
                wait: true,
                success: function() {
                    this.trigger('remove');
                }.bind(this)
            });
            
            // Fetch with params
            this.model.fetch({
                data: {
                    select: 'name,email,status'
                }
            });
        },
        
        testRelationshipOperations: function() {
            // Link related
            Espo.Ajax.postRequest('Account/' + accountId + '/contacts', {
                id: contactId
            });
            
            // Unlink related
            Espo.Ajax.deleteRequest('Account/' + accountId + '/contacts/' + contactId);
            
            // Get related
            Espo.Ajax.getRequest('Account/' + accountId + '/opportunities', {
                maxSize: 20,
                offset: 0,
                orderBy: 'createdAt',
                order: 'desc'
            });
        },
        
        testActionRequests: function() {
            // Custom actions
            Espo.Ajax.postRequest('Email/action/sendTest', {
                id: emailId
            });
            
            Espo.Ajax.postRequest('Lead/action/convert', {
                id: leadId,
                records: {
                    Account: accountData,
                    Contact: contactData
                }
            });
            
            // Mass actions
            Espo.Ajax.postRequest('Contact/action/massUpdate', {
                ids: selectedIds,
                values: {
                    assignedUserId: userId
                }
            });
        },
        
        testWebSocket: function() {
            // WebSocket subscription
            this.getHelper().webSocketManager.subscribe('notification', (event) => {
                this.handleNotification(event);
            });
            
            // WebSocket emit
            this.getHelper().webSocketManager.emit('message', {
                topic: 'user-activity',
                data: {
                    action: 'view',
                    entity: 'Account',
                    id: accountId
                }
            });
        },
        
        testFetchAPI: function() {
            // Modern fetch API
            fetch('/api/v1/Account', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            }).then(response => response.json());
            
            // With authentication
            fetch('/api/v1/User/current', {
                headers: {
                    'Authorization': 'Bearer ' + token
                }
            });
        }
    });
});