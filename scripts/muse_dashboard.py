import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time, streamlit as st
from eeg_muse.realtime import stream_and_predict

st.set_page_config(page_title='Muse Mental State', layout='centered')
st.title('Muse 2 Mental State (RandomForest)')
placeholder = st.empty()

def main():
    st.sidebar.header('Settings')
    artifacts_dir = st.sidebar.text_input('Artifacts dir', 'artifacts')
    model_path = st.sidebar.text_input('Model path (optional)', '')
    stream_name = st.sidebar.text_input('LSL stream name', 'Muse')
    channels = st.sidebar.text_input('Channels (space-separated)', 'TP9 AF7 AF8 TP10').split()
    window_sec = st.sidebar.number_input('Window (sec)', 0.5, 10.0, 2.0, 0.5)
    step_sec = st.sidebar.number_input('Step (sec)', 0.1, 5.0, 0.5, 0.1)
    st.sidebar.write('Start `muselsl stream` in another terminal before pressing Start.')
    if st.sidebar.button('Start'):
        for label, probs in stream_and_predict(artifacts_dir, model_path or None, stream_name, tuple(channels), window_sec, step_sec):
            with placeholder.container():
                st.subheader(f'Prediction: **{label}**')
                for k,v in probs.items():
                    st.metric(k, f'{v:.2f}')
                st.progress(min(1.0, max(probs.values())))
            time.sleep(0.01)

if __name__ == '__main__':
    main()
