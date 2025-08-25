#!/usr/bin/env python3
"""
Command-line interface for the Universal Code Graph System.
"""

import click
import json
import yaml
import sys
from pathlib import Path
from typing import Optional, List
import logging
from tqdm import tqdm

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from code_graph_system.core.plugin_manager import PluginManager
from code_graph_system.core.graph_store import FederatedGraphStore
from code_graph_system.core.plugin_interface import ParseResult


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.group()
@click.option('--config', '-c', default='config.yaml', help='Configuration file')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.pass_context
def cli(ctx, config, verbose):
    """Universal Code Graph System - Analyze any codebase"""
    ctx.ensure_object(dict)
    
    # Load configuration
    config_path = Path(config)
    if config_path.exists():
        with open(config_path) as f:
            ctx.obj['config'] = yaml.safe_load(f)
    else:
        ctx.obj['config'] = {
            'neo4j': {
                'uri': 'bolt://localhost:7688',
                'username': 'neo4j',
                'password': 'password123'
            },
            'plugins': {
                'directories': ['./plugins']
            }
        }
    
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        

@cli.command()
@click.argument('path')
@click.option('--language', '-l', help='Language to analyze (auto-detect if not specified)')
@click.option('--incremental', '-i', is_flag=True, help='Incremental analysis (only changed files)')
@click.option('--parallel', '-p', default=4, help='Number of parallel workers')
@click.pass_context
def analyze(ctx, path, language, incremental, parallel):
    """Analyze a codebase and build the graph"""
    config = ctx.obj['config']
    
    # Initialize components
    plugin_manager = PluginManager(config)
    graph_store = FederatedGraphStore(
        config['neo4j']['uri'],
        (config['neo4j']['username'], config['neo4j']['password']),
        config
    )
    
    # Load plugins
    click.echo("Loading plugins...")
    
    # Load PHP plugin
    php_plugin_path = Path(__file__).parent.parent / 'plugins' / 'php'
    if php_plugin_path.exists():
        sys.path.insert(0, str(php_plugin_path.parent))
        from php.plugin import PHPLanguagePlugin
        php_plugin = PHPLanguagePlugin()
        php_plugin.initialize({})
        plugin_manager.plugins['php-language'] = php_plugin
        plugin_manager.language_plugins['php'] = ['php-language']
        click.echo("✓ Loaded PHP plugin")
    
    # Load JavaScript plugin (would be similar)
    # js_plugin_path = Path(__file__).parent.parent / 'plugins' / 'javascript'
    # ...
    
    # Discover files
    project_path = Path(path)
    if not project_path.exists():
        click.echo(f"Error: Path {path} does not exist", err=True)
        return
        
    click.echo(f"Analyzing {project_path.absolute()}...")
    
    # Find all files
    php_files = list(project_path.rglob('*.php'))
    js_files = list(project_path.rglob('*.js'))
    
    total_files = len(php_files) + len(js_files)
    click.echo(f"Found {len(php_files)} PHP files and {len(js_files)} JS files")
    
    if total_files == 0:
        click.echo("No files to analyze")
        return
        
    # Process files
    nodes_count = 0
    relationships_count = 0
    errors = []
    
    with click.progressbar(php_files + js_files, label='Processing files') as files:
        for file_path in files:
            try:
                # Get appropriate plugin
                handler = plugin_manager.get_language_handler(str(file_path))
                
                if handler:
                    # Parse file
                    parse_result = handler.parse_file(str(file_path))
                    
                    # Store in graph
                    language = 'php' if str(file_path).endswith('.php') else 'javascript'
                    n, r = graph_store.store_batch(
                        parse_result.nodes,
                        parse_result.relationships,
                        language
                    )
                    nodes_count += n
                    relationships_count += r
                    
                    # Track errors
                    if parse_result.errors:
                        errors.extend(parse_result.errors)
                        
            except Exception as e:
                errors.append(f"Error processing {file_path}: {e}")
                logger.error(f"Failed to process {file_path}: {e}")
                
    # Print summary
    click.echo(f"\n✓ Analysis complete!")
    click.echo(f"  Nodes created: {nodes_count}")
    click.echo(f"  Relationships created: {relationships_count}")
    
    if errors:
        click.echo(f"  Errors: {len(errors)}")
        if click.confirm("Show errors?"):
            for error in errors[:10]:  # Show first 10 errors
                click.echo(f"    - {error}")
                

@cli.command()
@click.option('--query', '-q', help='Cypher query to execute')
@click.option('--file', '-f', type=click.File('r'), help='Query from file')
@click.option('--format', '-F', type=click.Choice(['json', 'table', 'csv']), default='table')
@click.pass_context
def query(ctx, query, file, format):
    """Query the code graph"""
    config = ctx.obj['config']
    
    # Initialize graph store
    graph_store = FederatedGraphStore(
        config['neo4j']['uri'],
        (config['neo4j']['username'], config['neo4j']['password']),
        config
    )
    
    # Get query
    if file:
        cypher = file.read()
    elif query:
        cypher = query
    else:
        click.echo("Enter query (Ctrl+D to execute):")
        cypher = sys.stdin.read()
        
    # Execute query
    try:
        results = graph_store.query(cypher)
        
        if format == 'json':
            click.echo(json.dumps(results, indent=2))
        elif format == 'csv':
            if results:
                import csv
                import sys
                writer = csv.DictWriter(sys.stdout, fieldnames=results[0].keys())
                writer.writeheader()
                writer.writerows(results)
        else:  # table
            if results:
                # Simple table output
                keys = results[0].keys()
                click.echo(" | ".join(keys))
                click.echo("-" * (len(" | ".join(keys))))
                for row in results:
                    click.echo(" | ".join(str(row.get(k, '')) for k in keys))
            else:
                click.echo("No results")
                
    except Exception as e:
        click.echo(f"Query error: {e}", err=True)
        

@cli.command()
@click.argument('target')
@click.option('--depth', '-d', default=3, help='Analysis depth')
@click.option('--direction', type=click.Choice(['in', 'out', 'both']), default='out')
@click.pass_context
def impact(ctx, target, depth, direction):
    """Analyze impact of changing a component"""
    config = ctx.obj['config']
    
    # Initialize graph store
    graph_store = FederatedGraphStore(
        config['neo4j']['uri'],
        (config['neo4j']['username'], config['neo4j']['password']),
        config
    )
    
    # Build impact query
    if direction == 'out':
        arrow = '->'
    elif direction == 'in':
        arrow = '<-'
    else:
        arrow = '-'
        
    cypher = f"""
        MATCH (n {{qualified_name: '{target}'}})
        MATCH path = (n){arrow}[*1..{depth}]{arrow}(m)
        RETURN DISTINCT m.qualified_name as affected, 
               labels(m)[0] as type,
               length(path) as distance
        ORDER BY distance, affected
        LIMIT 100
    """
    
    try:
        results = graph_store.query(cypher)
        
        if results:
            click.echo(f"Impact analysis for {target}:")
            click.echo(f"Found {len(results)} affected components:\n")
            
            current_distance = 0
            for result in results:
                if result['distance'] != current_distance:
                    current_distance = result['distance']
                    click.echo(f"\nDistance {current_distance}:")
                    
                click.echo(f"  - {result['affected']} ({result['type']})")
        else:
            click.echo(f"No impact found for {target}")
            
    except Exception as e:
        click.echo(f"Impact analysis error: {e}", err=True)
        

@cli.command()
@click.pass_context
def stats(ctx):
    """Show graph statistics"""
    config = ctx.obj['config']
    
    # Initialize graph store
    graph_store = FederatedGraphStore(
        config['neo4j']['uri'],
        (config['neo4j']['username'], config['neo4j']['password']),
        config
    )
    
    try:
        stats = graph_store.get_statistics()
        
        click.echo("Graph Statistics:")
        click.echo(f"  Total nodes: {stats['total_nodes']}")
        click.echo(f"  Total relationships: {stats['total_relationships']}")
        
        if stats.get('node_types'):
            click.echo("\nNode types:")
            for node_type, count in stats['node_types'].items():
                click.echo(f"    {node_type}: {count}")
                
        if stats.get('relationship_types'):
            click.echo("\nRelationship types:")
            for rel_type, count in stats['relationship_types'].items():
                click.echo(f"    {rel_type}: {count}")
                
        if stats.get('languages'):
            click.echo("\nLanguages:")
            for language, count in stats['languages'].items():
                click.echo(f"    {language}: {count}")
                
    except Exception as e:
        click.echo(f"Statistics error: {e}", err=True)
        

@cli.command()
@click.option('--language', '-l', help='Language to clear (all if not specified)')
@click.option('--confirm', is_flag=True, help='Skip confirmation')
@click.pass_context
def clear(ctx, language, confirm):
    """Clear the graph database"""
    config = ctx.obj['config']
    
    if not confirm:
        if not click.confirm(f"Clear {'all' if not language else language} graph data?"):
            return
            
    # Initialize graph store
    graph_store = FederatedGraphStore(
        config['neo4j']['uri'],
        (config['neo4j']['username'], config['neo4j']['password']),
        config
    )
    
    try:
        if language:
            graph_store.clear_language_graph(language)
            click.echo(f"Cleared {language} graph")
        else:
            graph_store.query("MATCH (n) DETACH DELETE n")
            click.echo("Cleared all graph data")
            
    except Exception as e:
        click.echo(f"Clear error: {e}", err=True)
        

@cli.command()
@click.argument('output_dir')
@click.option('--language', '-l', help='Language to export')
@click.pass_context
def export(ctx, output_dir, language):
    """Export graph to CSV files"""
    config = ctx.obj['config']
    
    # Initialize graph store
    graph_store = FederatedGraphStore(
        config['neo4j']['uri'],
        (config['neo4j']['username'], config['neo4j']['password']),
        config
    )
    
    try:
        graph_store.export_csv(output_dir, language)
        click.echo(f"Exported graph to {output_dir}")
        
    except Exception as e:
        click.echo(f"Export error: {e}", err=True)
        

@cli.command()
@click.pass_context
def plugins(ctx):
    """List available plugins"""
    config = ctx.obj['config']
    
    plugin_manager = PluginManager(config)
    
    # Discover plugins
    discovered = plugin_manager.discover_plugins()
    
    click.echo("Available plugins:")
    
    # List built-in plugins
    plugin_dir = Path(__file__).parent.parent / 'plugins'
    if plugin_dir.exists():
        for plugin_path in plugin_dir.iterdir():
            if plugin_path.is_dir():
                config_file = plugin_path / 'plugin.yaml'
                if config_file.exists():
                    with open(config_file) as f:
                        plugin_config = yaml.safe_load(f)
                        
                    click.echo(f"\n  {plugin_config['id']}:")
                    click.echo(f"    Name: {plugin_config['name']}")
                    click.echo(f"    Version: {plugin_config['version']}")
                    click.echo(f"    Type: {plugin_config['type']}")
                    click.echo(f"    Languages: {', '.join(plugin_config.get('supported_languages', []))}")
                    

def main():
    """Main entry point"""
    cli(obj={})
    

if __name__ == '__main__':
    main()