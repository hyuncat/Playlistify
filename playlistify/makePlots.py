import pandas as pd
import plotly.express as px




def playlist_bar(song_df, value, playlist_name, n_ticks=None):
    # Filter the dataframe based on the number of ticks if specified
    if n_ticks is not None:
        song_df = song_df.head(n_ticks)
    
    # Create the bar graph using Plotly Express
    fig = px.bar(song_df, x='song_title', y=value, title=f"{playlist_name}: {value}",
                 labels={'song_title': "Song", value: value.capitalize()})
    
    # Adjust x-axis tick labels
    if n_ticks is not None:
        fig.update_layout(xaxis=dict(tickmode='linear', tick0=0, dtick=1))

    # Show the plot
    fig.show()

# Example usage
if __name__ == "__main__":
    # Sample data
    data = pd.read_csv('playlistify/static/tiger_talk_songs.csv')
    print(data.head())
    playlist_bar(data, "popularity", "tiger talk", 10)