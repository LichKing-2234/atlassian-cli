import typer

app = typer.Typer(help="Atlassian Server/Data Center CLI")

jira_app = typer.Typer(help="Jira commands")
confluence_app = typer.Typer(help="Confluence commands")
bitbucket_app = typer.Typer(help="Bitbucket commands")

app.add_typer(jira_app, name="jira")
app.add_typer(confluence_app, name="confluence")
app.add_typer(bitbucket_app, name="bitbucket")
