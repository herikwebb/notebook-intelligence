// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import React, { useMemo, useState } from 'react';

export function AskUserQuestion(props: any) {
  const userQuestions = props.userQuestions.content;
  const [selectedAnswers, setSelectedAnswers] = useState<{
    [key: string]: string[];
  }>({});

  // Form-scoped id prefix so DOM ids stay unique even when two questions
  // share label text (or several AskUserQuestion forms render in the same
  // chat transcript). Falls back to a render-stable random suffix when
  // the form-level identifier is absent.
  const formIdPrefix = useMemo(() => {
    const id = userQuestions.identifier?.id;
    if (typeof id === 'string' && id.length > 0) {
      return `nbi-auq-${id}`;
    }
    return `nbi-auq-${Math.random().toString(36).slice(2, 10)}`;
  }, [userQuestions.identifier?.id]);

  const onOptionSelected = (question: any, option: any) => {
    if (question.multiSelect) {
      if (selectedAnswers[question.question]?.includes(option.label)) {
        setSelectedAnswers({
          ...selectedAnswers,
          [question.question]: (
            selectedAnswers[question.question] ?? []
          ).filter((o: any) => o !== option.label)
        });
      } else {
        setSelectedAnswers({
          ...selectedAnswers,
          [question.question]: [
            ...(selectedAnswers[question.question] ?? []),
            option.label
          ]
        });
      }
    } else {
      setSelectedAnswers({
        ...selectedAnswers,
        [question.question]: [option.label]
      });
    }
  };

  return (
    <>
      {userQuestions.title ? (
        <div>
          <b>{userQuestions.title}</b>
        </div>
      ) : null}
      {userQuestions.message ? <div>{userQuestions.message}</div> : null}
      {userQuestions.questions.map((question: any, qIndex: number) => {
        const questionDomId = `${formIdPrefix}-q${qIndex}`;
        // A single-select group is a radio group with a shared name so
        // screen readers announce "1 of N selected" rather than treating
        // each option as an independent checkbox.
        const inputType = question.multiSelect ? 'checkbox' : 'radio';
        return (
          <div
            className="ask-user-question-container"
            key={questionDomId}
            role="group"
            aria-labelledby={`${questionDomId}-label`}
          >
            <form className="ask-user-question-form">
              <div
                className="ask-user-question-question"
                id={`${questionDomId}-label`}
              >
                {question.question}
              </div>
              <div className="ask-user-question-header">{question.header}</div>
              <div className="ask-user-question-options">
                {question.options.map((option: any, oIndex: number) => {
                  const optionDomId = `${questionDomId}-o${oIndex}`;
                  return (
                    <div className="ask-user-question-option" key={optionDomId}>
                      <div className="ask-user-question-option-input-container">
                        <input
                          id={optionDomId}
                          name={questionDomId}
                          type={inputType}
                          checked={
                            selectedAnswers[question.question]?.includes(
                              option.label
                            ) ?? false
                          }
                          onChange={() => onOptionSelected(question, option)}
                        />
                        <label
                          htmlFor={optionDomId}
                          className="ask-user-question-option-label-container"
                        >
                          <div className="ask-user-question-option-label">
                            {option.label}
                          </div>
                          <div className="ask-user-question-option-description">
                            {option.description}
                          </div>
                        </label>
                      </div>
                    </div>
                  );
                })}
              </div>
            </form>
          </div>
        );
      })}
      <div className="ask-user-question-footer">
        <button
          className="jp-Dialog-button jp-mod-accept jp-mod-styled"
          onClick={() => {
            props.onSubmit(selectedAnswers);
          }}
        >
          <div className="jp-Dialog-buttonLabel">
            {userQuestions.submitLabel}
          </div>
        </button>
        <button
          className="jp-Dialog-button jp-mod-reject jp-mod-styled"
          onClick={() => {
            props.onCancel();
          }}
        >
          <div className="jp-Dialog-buttonLabel">
            {userQuestions.cancelLabel}
          </div>
        </button>
      </div>
    </>
  );
}
