import chess
import chess.svg
import streamlit as st
from autogen import ConversableAgent, register_function

if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = None
if "board" not in st.session_state:
    st.session_state.board = chess.Board()
if "made_move" not in st.session_state:
    st.session_state.made_move = False
if "board_svg" not in st.session_state:
    st.session_state.board_svg = None
if "move_history" not in st.session_state:
    st.session_state.move_history = []
if "max_turns" not in st.session_state:
    st.session_state.max_turns = 5

st.sidebar.title("Chess Agent Configuration")
api_key = st.sidebar.text_input("Enter your API key (OpenAI, Groq, Gemini, etc.):", type="password")
if api_key:
    st.session_state.openai_api_key = api_key
    st.sidebar.success("API key saved!")

model_options = [
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gpt-4o-mini",
    "gpt-4o",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
    "Custom..."
]
selected_model = st.sidebar.selectbox("Select Model:", model_options)
if selected_model == "Custom...":
    model_name = st.sidebar.text_input("Enter Custom Model Name:", value="gpt-4o-mini")
else:
    model_name = selected_model
base_url = st.sidebar.text_input("API Base URL (Leave empty for default OpenAI. Use https://api.groq.com/openai/v1 for Groq, https://api.x.ai/v1 for xAI Grok):", value="")


st.sidebar.info("""
For a complete chess game with potential checkmate, it would take max_turns > 200 approximately.
However, this will consume significant API credits and a lot of time.
For demo purposes, using 5-10 turns is recommended.
""")

max_turns_input = st.sidebar.number_input(
    "Enter the number of turns (max_turns):",
    min_value=1,
    max_value=1000,
    value=st.session_state.max_turns,
    step=1
)

if max_turns_input:
    st.session_state.max_turns = max_turns_input
    st.sidebar.success(f"Max turns of total chess moves set to {st.session_state.max_turns}!")

st.title("PromptMate: Multi-Agent AI Chess")

def available_moves() -> str:
    """
    Call this tool to get a list of all legal moves in the current position.
    The moves will be returned in UCI format (e.g. 'e2e4').
    """
    available_moves = [str(move) for move in st.session_state.board.legal_moves]
    return "Available moves are: " + ",".join(available_moves)

def execute_move(move: str) -> str:
    """
    Call this tool to make a move on the board.
    The move MUST be in UCI format (e.g., 'e2e4', 'g1f3').
    Standard algebraic notation (SAN) like 'Nf6' will fail.
    """
    try:
        chess_move = chess.Move.from_uci(move)
        if chess_move not in st.session_state.board.legal_moves:
            return f"Invalid move: {move}. Please call available_moves() to see valid moves."
        
        # Update board state
        st.session_state.board.push(chess_move)
        st.session_state.made_move = True
        board_svg = chess.svg.board(st.session_state.board, size=400)
        st.session_state.move_history.append(board_svg)
        st.session_state.made_move = True
        
        # Real-time UI Update!
        if "board_placeholder" in st.session_state:
            import base64
            b64 = base64.b64encode(board_svg.encode('utf-8')).decode("utf-8")
            html = f'<img src="data:image/svg+xml;base64,{b64}"/>'
            st.session_state.board_placeholder.markdown(html, unsafe_allow_html=True)

        # Get piece information
        moved_piece = st.session_state.board.piece_at(chess_move.to_square)
        piece_unicode = moved_piece.unicode_symbol()
        piece_type_name = chess.piece_name(moved_piece.piece_type)
        piece_name = piece_type_name.capitalize() if piece_unicode.isupper() else piece_type_name
        
        # Generate move description
        from_square = chess.SQUARE_NAMES[chess_move.from_square]
        to_square = chess.SQUARE_NAMES[chess_move.to_square]
        move_desc = f"Moved {piece_name} ({piece_unicode}) from {from_square} to {to_square}."
        if st.session_state.board.is_checkmate():
            winner = 'White' if st.session_state.board.turn == chess.BLACK else 'Black'
            move_desc += f"\nCheckmate! {winner} wins!"
        elif st.session_state.board.is_stalemate():
            move_desc += "\nGame ended in stalemate!"
        elif st.session_state.board.is_insufficient_material():
            move_desc += "\nGame ended - insufficient material to checkmate!"
        elif st.session_state.board.is_check():
            move_desc += "\nCheck!"

        return move_desc
    except ValueError:
        return f"Invalid move format: {move}. Please use UCI format (e.g., 'e2e4')."

def check_made_move(msg):
    if st.session_state.made_move:
        st.session_state.made_move = False
        return True
    else:
        return False

if st.session_state.openai_api_key:
    try:
        # Auto-detect Groq and Gemini keys
        actual_base_url = base_url
        if st.session_state.openai_api_key:
            if st.session_state.openai_api_key.startswith("gsk_"):
                actual_base_url = "https://api.groq.com/openai/v1"
            elif st.session_state.openai_api_key.startswith("AIza") or "gemini" in model_name.lower():
                actual_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"

        agent_white_config_list = [
            {
                "model": model_name,
                "api_key": st.session_state.openai_api_key,
            },
        ]
        if actual_base_url:
            agent_white_config_list[0]["base_url"] = actual_base_url
            agent_white_config_list[0]["api_type"] = "openai"

        agent_black_config_list = [
            {
                "model": model_name,
                "api_key": st.session_state.openai_api_key,
            },
        ]
        if actual_base_url:
            agent_black_config_list[0]["base_url"] = actual_base_url
            agent_black_config_list[0]["api_type"] = "openai"

        agent_white = ConversableAgent(
            name="Agent_White",  
            system_message="You are a professional chess player and you play as white. "
            "You MUST use UCI format for all moves (e.g. 'e2e4', 'g1f3'). "
            "First call available_moves() first, to get list of legal available moves. "
            "Then call execute_move(move) to make a move.",
            llm_config={"config_list": agent_white_config_list, "cache_seed": None},
        )

        agent_black = ConversableAgent(
            name="Agent_Black",  
            system_message="You are a professional chess player and you play as black. "
            "You MUST use UCI format for all moves (e.g. 'e2e4', 'g1f3'). "
            "First call available_moves() first, to get list of legal available moves. "
            "Then call execute_move(move) to make a move.",
            llm_config={"config_list": agent_black_config_list, "cache_seed": None},
        )

        game_master = ConversableAgent(
            name="Game_Master",  
            llm_config=False,
            is_termination_msg=check_made_move,
            default_auto_reply="Please make a move.",
            human_input_mode="NEVER",
        )

        register_function(
            execute_move,
            caller=agent_white,
            executor=game_master,
            name="execute_move",
            description="Call this tool to make a move.",
        )

        register_function(
            available_moves,
            caller=agent_white,
            executor=game_master,
            name="available_moves",
            description="Get legal moves.",
        )

        register_function(
            execute_move,
            caller=agent_black,
            executor=game_master,
            name="execute_move",
            description="Call this tool to make a move.",
        )

        register_function(
            available_moves,
            caller=agent_black,
            executor=game_master,
            name="available_moves",
            description="Get legal moves.",
        )

        agent_white.register_nested_chats(
            trigger=agent_black,
            chat_queue=[
                {
                    "sender": game_master,
                    "recipient": agent_white,
                    "summary_method": "last_msg",
                    "max_turns": 5,
                }
            ],
        )

        agent_black.register_nested_chats(
            trigger=agent_white,
            chat_queue=[
                {
                    "sender": game_master,
                    "recipient": agent_black,
                    "summary_method": "last_msg",
                    "max_turns": 5,
                }
            ],
        )

        st.info(f"""
This chess game is played between two AG2 AI agents:
- **Agent White**: A {model_name} powered chess player controlling white pieces
- **Agent Black**: A {model_name} powered chess player controlling black pieces

The game is managed by a **Game Master** that:
- Validates all moves
- Updates the chess board
- Manages turn-taking between players
- Provides legal move information
""")

        initial_board_svg = chess.svg.board(st.session_state.board, size=300)
        st.subheader("Initial Board")
        st.image(initial_board_svg)

        if st.button("Start Game"):
            st.session_state.board.reset()
            st.session_state.made_move = False
            st.session_state.move_history = []
            st.session_state.board_svg = chess.svg.board(st.session_state.board, size=300)
            st.info("The AI agents will now play against each other. Each agent will analyze the board, " 
                   "request legal moves from the Game Master (proxy agent), and make strategic decisions.")
            st.success("You can view the interaction between the agents in the terminal output, but you can also watch the live board below!")
            st.write("Game started! White's turn.")

            st.write("### Live Board")
            st.session_state.board_placeholder = st.empty()
            
            # Draw initial board
            initial_svg = chess.svg.board(st.session_state.board, size=400)
            import base64
            b64 = base64.b64encode(initial_svg.encode('utf-8')).decode("utf-8")
            st.session_state.board_placeholder.markdown(f'<img src="data:image/svg+xml;base64,{b64}"/>', unsafe_allow_html=True)

            with st.spinner(f"Agents are playing {st.session_state.max_turns} turns... Check the terminal for live thoughts and tool calls!"):
                chat_result = agent_black.initiate_chat(
                    recipient=agent_white, 
                    message="Let's play chess! You go first, its your move.",
                    max_turns=st.session_state.max_turns,
                    summary_method="reflection_with_llm"
                )
            st.markdown(chat_result.summary)

            if st.session_state.move_history:
                st.success(f"Game completed! Total moves made: {len(st.session_state.move_history)}")
                
                # Display the Game Summary / PGN
                st.subheader("Game Summary (PGN)")
                import chess.pgn
                game = chess.pgn.Game.from_board(st.session_state.board)
                game.headers["Event"] = "PromptMate Match"
                game.headers["White"] = "Agent White"
                game.headers["Black"] = "Agent Black"
                st.code(str(game.mainline_moves()), language="text")

                # Display the visual move history
                st.subheader("Visual Move History")
                for i, move_svg in enumerate(st.session_state.move_history):
                    move_by = "Agent White" if i % 2 == 0 else "Agent Black"
                    st.write(f"### Move {i + 1} by {move_by}")
                    
                    # Convert SVG to base64 for history display
                    b64 = base64.b64encode(move_svg.encode('utf-8')).decode("utf-8")
                    st.markdown(f'<img src="data:image/svg+xml;base64,{b64}"/>', unsafe_allow_html=True)

        if st.button("Reset Game"):
            st.session_state.board.reset()
            st.session_state.made_move = False
            st.session_state.move_history = []
            st.session_state.board_svg = None
            st.write("Game reset! Click 'Start Game' to begin a new game.")

    except Exception as e:
        import traceback
        st.error(f"An error occurred: {e}. Please check your API key and try again.")
        st.error(f"```python\n{traceback.format_exc()}\n```")

else:
    st.warning("Please enter your API key in the sidebar to start the game.")