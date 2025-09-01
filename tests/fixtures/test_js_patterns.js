/**
 * Test file for EspoCRM JavaScript pattern detection
 */

import BaseView from 'views/base';
import Model from 'model';
import Ajax from 'ajax';

// Test 1: ES6 Class extending Backbone View
class LeadDetailView extends BaseView {
    
    template = 'crm:lead/detail.tpl'
    
    constructor() {
        super();
        
        // Test 2: Event handlers
        this.listenTo(this.model, 'change:status', this.onStatusChange);
        this.on('render', this.afterRender);
        
        // Test 3: API calls
        Ajax.postRequest('Lead/action/convert', {
            id: this.model.id,
            data: payload
        }).then(response => {
            this.trigger('converted', response);
        });
        
        // Test 4: Dynamic require
        require(['views/' + this.viewName], View => {
            this.createView('dialog', View, options);
        });
    }
    
    afterRender() {
        // Test 5: Another API call pattern
        Espo.Ajax.getRequest('Lead/' + this.model.id).then(data => {
            this.model.set(data);
        });
        
        // Test 6: Template reference
        this.templateContent = this.getTemplate('crm:lead/fields/status.tpl');
    }
    
    onStatusChange() {
        // Test 7: Event triggering
        this.trigger('status:changed', this.model.get('status'));
        
        // Test 8: Stop listening
        this.stopListening(this.model, 'change:name');
    }
}

// Test 9: Backbone Model pattern
const LeadModel = Backbone.Model.extend({
    
    urlRoot: 'Lead',
    
    // Test 10: Events hash
    events: {
        'click .action-convert': 'actionConvert',
        'change .field-status': 'onStatusFieldChange'
    },
    
    initialize: function() {
        // Test 11: Model event binding
        this.on('sync', this.afterSync, this);
        this.once('destroy', this.cleanup);
    },
    
    actionConvert: function() {
        // Test 12: DELETE request
        Ajax.deleteRequest('Lead/' + this.id).then(() => {
            this.trigger('deleted');
        });
    },
    
    afterSync: function() {
        // Test 13: PUT request
        Ajax.putRequest('Lead/' + this.id, this.attributes);
    }
});

// Test 14: Backbone Collection
const LeadCollection = Backbone.Collection.extend({
    model: LeadModel,
    url: 'Lead/list',
    
    initialize: function() {
        // Test 15: Collection events
        this.listenTo(this, 'add', this.onAdd);
        this.listenTo(this, 'remove', this.onRemove);
    }
});

// Test 16: AMD module with dynamic dependencies
define(['views/record/detail'], function(DetailView) {
    
    return DetailView.extend({
        
        template: 'custom:templates/lead-detail',
        
        setup: function() {
            // Test 17: Complex dynamic require
            const modules = ['views/' + this.scope + '/detail'];
            
            require(modules, function(View) {
                this.createView('main', View);
            }.bind(this));
            
            // Test 18: PATCH request
            Espo.Ajax.patchRequest('Lead/' + this.model.id, {
                status: 'Converted'
            });
        }
    });
});

// Test 19: Router with events
const AppRouter = Backbone.Router.extend({
    routes: {
        'lead/:id': 'showLead',
        'lead/:id/edit': 'editLead'
    },
    
    showLead: function(id) {
        // Test 20: GET with query params
        Ajax.getRequest('Lead/' + id, {
            params: {
                select: 'id,name,status'
            }
        });
    }
});